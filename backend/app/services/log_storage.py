from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.db import get_connection
from app.parsers.acs_log_parser import _detect_acs_node


@dataclass
class LogFileRecord:
    id: int
    log_date: str
    acs_node: str
    filename: str
    file_size: int
    storage_path: str
    uploaded_at: str


def get_log_storage_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    default = root / "data" / "logs"
    storage_dir = Path(os.getenv("LOG_STORAGE_DIR", str(default)))
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def parse_log_filename(filename: str) -> tuple[str, str]:
    acs_node = _detect_acs_node(filename)
    if not acs_node:
        raise ValueError(f"Log file name must include ACS1 or ACS2: {filename}")

    dates = re.findall(r"(\d{4}-\d{2}-\d{2})", filename)
    if not dates:
        raise ValueError(f"Cannot detect date in log file name: {filename}")

    return dates[0], acs_node


def _row_to_record(row: dict) -> LogFileRecord:
    uploaded_at = row["uploaded_at"]
    return LogFileRecord(
        id=row["id"],
        log_date=str(row["log_date"]),
        acs_node=row["acs_node"],
        filename=row["filename"],
        file_size=row["file_size"],
        storage_path=row["storage_path"],
        uploaded_at=uploaded_at.isoformat() if hasattr(uploaded_at, "isoformat") else str(uploaded_at),
    )


def _record_to_dict(record: LogFileRecord) -> dict:
    return {
        "id": record.id,
        "logDate": record.log_date,
        "acsNode": record.acs_node,
        "filename": record.filename,
        "fileSize": record.file_size,
        "uploadedAt": record.uploaded_at,
    }


def save_upload(filename: str, content: bytes) -> dict:
    log_date, acs_node = parse_log_filename(filename)
    storage_dir = get_log_storage_dir()
    day_dir = storage_dir / log_date
    day_dir.mkdir(parents=True, exist_ok=True)
    storage_path = day_dir / f"{acs_node}.log"
    storage_path.write_bytes(content)

    relative_path = str(storage_path.relative_to(storage_dir))

    with get_connection() as connection:
        old_row = connection.execute(
            """
            SELECT storage_path
            FROM log_file
            WHERE log_date = %s AND acs_node = %s
            """,
            (log_date, acs_node),
        ).fetchone()

        row = connection.execute(
            """
            INSERT INTO log_file (log_date, acs_node, filename, file_size, storage_path)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (log_date, acs_node) DO UPDATE SET
                filename = EXCLUDED.filename,
                file_size = EXCLUDED.file_size,
                storage_path = EXCLUDED.storage_path,
                uploaded_at = now()
            RETURNING id, log_date, acs_node, filename, file_size, storage_path, uploaded_at
            """,
            (log_date, acs_node, filename, len(content), relative_path),
        ).fetchone()
        connection.commit()

    if old_row and old_row["storage_path"] != relative_path:
        old_path = storage_dir / old_row["storage_path"]
        if old_path.exists() and old_path != storage_path:
            old_path.unlink(missing_ok=True)

    return _record_to_dict(_row_to_record(row))


def list_log_files(log_date: str | None = None) -> list[dict]:
    query = """
        SELECT id, log_date, acs_node, filename, file_size, storage_path, uploaded_at
        FROM log_file
    """
    params: tuple[str, ...] = ()
    if log_date:
        query += " WHERE log_date = %s"
        params = (log_date,)
    query += " ORDER BY log_date DESC, acs_node ASC"

    with get_connection(readonly=True) as connection:
        rows = connection.execute(query, params).fetchall()

    return [_record_to_dict(_row_to_record(row)) for row in rows]


def list_log_days() -> list[dict]:
    with get_connection(readonly=True) as connection:
        rows = connection.execute(
            """
            SELECT
                log_date,
                bool_or(acs_node = 'acs1') AS acs1,
                bool_or(acs_node = 'acs2') AS acs2
            FROM log_file
            GROUP BY log_date
            ORDER BY log_date DESC
            """
        ).fetchall()

    return [
        {
            "date": str(row["log_date"]),
            "acs1": bool(row["acs1"]),
            "acs2": bool(row["acs2"]),
            "complete": bool(row["acs1"]) and bool(row["acs2"]),
        }
        for row in rows
    ]


def read_log_files_by_ids(file_ids: list[int]) -> list[tuple[str, str]]:
    if not file_ids:
        raise ValueError("No log files selected.")

    storage_dir = get_log_storage_dir()
    unique_ids = sorted(set(file_ids))

    with get_connection(readonly=True) as connection:
        rows = connection.execute(
            """
            SELECT id, filename, storage_path
            FROM log_file
            WHERE id = ANY(%s)
            ORDER BY log_date, acs_node
            """,
            (unique_ids,),
        ).fetchall()

    if len(rows) != len(unique_ids):
        found_ids = {row["id"] for row in rows}
        missing = [file_id for file_id in unique_ids if file_id not in found_ids]
        raise ValueError(f"Log file(s) not found: {', '.join(str(file_id) for file_id in missing)}")

    parsed_files: list[tuple[str, str]] = []
    for row in rows:
        path = storage_dir / row["storage_path"]
        if not path.exists():
            raise ValueError(f"Stored log file missing on disk: {row['filename']}")
        parsed_files.append((row["filename"], path.read_text(encoding="utf-8", errors="ignore")))

    return parsed_files


def delete_log_file(file_id: int) -> None:
    storage_dir = get_log_storage_dir()

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT storage_path
            FROM log_file
            WHERE id = %s
            """,
            (file_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Log file not found: {file_id}")

        connection.execute("DELETE FROM log_file WHERE id = %s", (file_id,))
        connection.commit()

    path = storage_dir / row["storage_path"]
    if path.exists():
        path.unlink()
