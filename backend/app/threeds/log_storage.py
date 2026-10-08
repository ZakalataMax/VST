from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.threeds.paths import get_log_storage_dir

ELASTIC_NODE = "elastic"


def _log_path(storage_dir: Path, log_date: str) -> Path:
    return storage_dir / log_date / f"{ELASTIC_NODE}.log"


def _meta_path(storage_dir: Path, log_date: str) -> Path:
    return storage_dir / log_date / f"{ELASTIC_NODE}.meta.json"


def _default_filename(log_date: str) -> str:
    return f"solar-3ds-server.{log_date}.log"


def has_elastic_log(log_date: str) -> bool:
    return _log_path(get_log_storage_dir(), log_date).exists()


def read_elastic_meta(log_date: str) -> dict | None:
    meta_path = _meta_path(get_log_storage_dir(), log_date)
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def elastic_download_complete(log_date: str) -> bool:
    if not has_elastic_log(log_date):
        return False
    meta = read_elastic_meta(log_date)
    if meta is None:
        return True
    return not bool(meta.get("partial", False))


def save_elastic_log(
    log_date: str,
    content: str,
    *,
    partial: bool,
    row_count: int = 0,
    min_datetime: str = "",
    max_datetime: str = "",
) -> dict:
    storage_dir = get_log_storage_dir()
    day_dir = storage_dir / log_date
    day_dir.mkdir(parents=True, exist_ok=True)
    log_path = _log_path(storage_dir, log_date)
    log_path.write_text(content, encoding="utf-8")
    filename = _default_filename(log_date)
    downloaded_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "filename": filename,
        "downloadedAt": downloaded_at,
        "partial": partial,
        "rowCount": row_count,
        "minDateTime": min_datetime,
        "maxDateTime": max_datetime,
    }
    _meta_path(storage_dir, log_date).write_text(json.dumps(meta), encoding="utf-8")
    return {
        "logDate": log_date,
        "filename": filename,
        "fileSize": log_path.stat().st_size,
        "uploadedAt": downloaded_at,
        "partial": partial,
        "rowCount": row_count,
    }


def list_log_days() -> list[dict]:
    storage_dir = get_log_storage_dir()
    days: list[dict] = []
    for day_dir in sorted(storage_dir.iterdir(), key=lambda path: path.name, reverse=True):
        if not day_dir.is_dir() or not _log_path(storage_dir, day_dir.name).exists():
            continue
        meta = read_elastic_meta(day_dir.name) or {}
        days.append(
            {
                "date": day_dir.name,
                "partial": bool(meta.get("partial", False)),
                "rowCount": int(meta.get("rowCount") or 0),
            }
        )
    return days


def read_log_content(log_date: str) -> str:
    log_path = _log_path(get_log_storage_dir(), log_date)
    if not log_path.exists():
        raise ValueError(f"No downloaded log for {log_date}")
    return log_path.read_text(encoding="utf-8", errors="replace")


def read_day_for_parse(log_date: str) -> list[tuple[str, str]]:
    storage_dir = get_log_storage_dir()
    log_path = _log_path(storage_dir, log_date)
    if not log_path.exists():
        raise ValueError(f"No downloaded log for {log_date}")
    meta = read_elastic_meta(log_date) or {}
    filename = meta.get("filename") or _default_filename(log_date)
    return [(filename, log_path.read_text(encoding="utf-8", errors="replace"))]


def delete_log_day(log_date: str) -> None:
    storage_dir = get_log_storage_dir()
    day_dir = storage_dir / log_date
    if day_dir.exists():
        shutil.rmtree(day_dir)
