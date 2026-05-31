from __future__ import annotations

from pathlib import Path

from app.parsers.models import CSV_COLUMNS

COMPARE_COLUMNS = [column for column in CSV_COLUMNS if column != "logFile"]


def normalize_log_file(value: str) -> str:
    return Path(value.replace("\\", "/")).name


def row_sort_key(row: dict[str, str]) -> tuple[str, ...]:
    normalized = {column: row.get(column, "") or "" for column in CSV_COLUMNS}
    normalized["logFile"] = normalize_log_file(normalized.get("logFile", ""))
    return tuple(normalized[column] for column in CSV_COLUMNS)
