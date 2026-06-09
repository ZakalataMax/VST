from __future__ import annotations

from app.services.report import format_report_cell_value

DEFAULT_WIDTH = 112
MIN_WIDTH = 48


def default_column_width(column: str) -> int:
    lower = column.lower()
    if "messagedatetime" in lower or "timestamp" in lower:
        return 168
    if "messagedate" in lower or lower.endswith("_date") or lower == "date":
        return 96
    if "transid" in lower or "transaction" in lower:
        return 136
    if "timeline" in lower:
        return 180
    if "agent" in lower or "useragent" in lower:
        return 200
    if lower.endswith("id") or "_id" in lower:
        return 120
    if "status" in lower or "type" in lower:
        return 88
    return DEFAULT_WIDTH


def should_elide(column: str, value: str) -> bool:
    if not value:
        return False
    limit = 36 if "agent" in column.lower() or "timeline" in column.lower() else 28
    return len(value) > limit
