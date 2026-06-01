from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.parsers.acs_log_parser import _detect_acs_node
from app.paths import get_log_storage_dir


@dataclass
class LogFileRecord:
    id: str
    log_date: str
    acs_node: str
    filename: str
    file_size: int
    storage_path: str
    uploaded_at: str


def parse_log_filename(filename: str) -> tuple[str, str]:
    acs_node = _detect_acs_node(filename)
    if not acs_node:
        raise ValueError(f"Log file name must include ACS1 or ACS2: {filename}")

    dates = re.findall(r"(\d{4}-\d{2}-\d{2})", filename)
    if not dates:
        raise ValueError(f"Cannot detect date in log file name: {filename}")

    return dates[0], acs_node


def make_file_id(log_date: str, acs_node: str) -> str:
    return f"{log_date}/{acs_node}"


def parse_file_id(file_id: str) -> tuple[str, str]:
    parts = file_id.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid log file id: {file_id}")
    return parts[0], parts[1]


def _storage_path_for(log_date: str, acs_node: str) -> str:
    return f"{log_date}/{acs_node}.log"


def _record_from_path(storage_dir: Path, log_date: str, acs_node: str, filename: str) -> LogFileRecord:
    relative_path = _storage_path_for(log_date, acs_node)
    path = storage_dir / relative_path
    uploaded_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    return LogFileRecord(
        id=make_file_id(log_date, acs_node),
        log_date=log_date,
        acs_node=acs_node,
        filename=filename,
        file_size=path.stat().st_size,
        storage_path=relative_path,
        uploaded_at=uploaded_at,
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


def _read_meta(day_dir: Path, acs_node: str) -> tuple[str, str] | None:
    meta_path = day_dir / f"{acs_node}.meta"
    if not meta_path.exists():
        return None
    lines = meta_path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return None
    return lines[0].strip(), lines[1].strip()


def save_upload(filename: str, content: bytes) -> dict:
    log_date, acs_node = parse_log_filename(filename)
    storage_dir = get_log_storage_dir()
    day_dir = storage_dir / log_date
    day_dir.mkdir(parents=True, exist_ok=True)
    storage_path = day_dir / f"{acs_node}.log"
    storage_path.write_bytes(content)
    meta_path = day_dir / f"{acs_node}.meta"
    meta_path.write_text(f"{filename}\n{datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")
    record = _record_from_path(storage_dir, log_date, acs_node, filename)
    return _record_to_dict(record)


def list_log_files(log_date: str | None = None) -> list[dict]:
    storage_dir = get_log_storage_dir()
    records: list[LogFileRecord] = []

    if log_date:
        day_dirs = [storage_dir / log_date] if (storage_dir / log_date).is_dir() else []
    else:
        day_dirs = sorted(
            (path for path in storage_dir.iterdir() if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        )

    for day_dir in day_dirs:
        date = day_dir.name
        for acs_node in ("acs1", "acs2"):
            log_path = day_dir / f"{acs_node}.log"
            if not log_path.exists():
                continue
            meta = _read_meta(day_dir, acs_node)
            filename = meta[0] if meta else f"{acs_node.upper()}_{date}.log"
            records.append(_record_from_path(storage_dir, date, acs_node, filename))

    return [_record_to_dict(record) for record in records]


def list_log_days() -> list[dict]:
    storage_dir = get_log_storage_dir()
    days: list[dict] = []

    for day_dir in sorted(storage_dir.iterdir(), key=lambda path: path.name, reverse=True):
        if not day_dir.is_dir():
            continue
        acs1 = (day_dir / "acs1.log").exists()
        acs2 = (day_dir / "acs2.log").exists()
        if not acs1 and not acs2:
            continue
        days.append(
            {
                "date": day_dir.name,
                "acs1": acs1,
                "acs2": acs2,
                "complete": acs1 and acs2,
            }
        )

    return days


def read_log_files_by_ids(file_ids: list[str]) -> list[tuple[str, str]]:
    if not file_ids:
        raise ValueError("No log files selected.")

    storage_dir = get_log_storage_dir()
    unique_ids = sorted(set(file_ids))
    parsed_files: list[tuple[str, str]] = []

    for file_id in unique_ids:
        log_date, acs_node = parse_file_id(file_id)
        path = storage_dir / _storage_path_for(log_date, acs_node)
        if not path.exists():
            raise ValueError(f"Log file not found: {file_id}")
        meta = _read_meta(storage_dir / log_date, acs_node)
        filename = meta[0] if meta else path.name
        parsed_files.append((filename, path.read_text(encoding="utf-8", errors="ignore")))

    return parsed_files


def delete_log_file(file_id: str) -> None:
    storage_dir = get_log_storage_dir()
    log_date, acs_node = parse_file_id(file_id)
    day_dir = storage_dir / log_date
    log_path = day_dir / f"{acs_node}.log"
    meta_path = day_dir / f"{acs_node}.meta"

    if not log_path.exists():
        raise ValueError(f"Log file not found: {file_id}")

    log_path.unlink(missing_ok=True)
    meta_path.unlink(missing_ok=True)

    if day_dir.exists() and not any(day_dir.iterdir()):
        day_dir.rmdir()
