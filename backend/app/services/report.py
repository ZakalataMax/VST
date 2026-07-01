from __future__ import annotations

import re
from dataclasses import dataclass

DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d{1,3})?$"
)
ISO_DATETIME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(.*)$")
UNDERSCORE_DATE = re.compile(r"^(\d{2})_(\d{2})_(\d{4})$")
FORBIDDEN_SQL = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY|"
    r"ATTACH|DETACH|INSTALL|LOAD|PRAGMA|SET|CALL|EXPORT|IMPORT|USE)\b",
    re.IGNORECASE,
)
FORBIDDEN_FUNCTIONS = re.compile(
    r"\b("
    r"read_csv|read_csv_auto|read_parquet|parquet_scan|read_json|read_json_auto|"
    r"read_json_objects|read_ndjson|read_ndjson_auto|read_text|read_blob|"
    r"csv_scan|glob|read_csv_gz"
    r")\s*\(",
    re.IGNORECASE,
)
DEFAULT_LIMIT = 500
MAX_LIMIT = 5000


@dataclass
class ReportResult:
    columns: list[str]
    rows: list[dict]
    row_count: int
    limit: int
    offset: int


def normalize_date_from(value: str) -> str:
    trimmed = value.strip()
    if DATE_ONLY_PATTERN.match(trimmed):
        return f"{trimmed} 00:00:00.000"
    return trimmed


def normalize_date_to(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    trimmed = value.strip()
    if DATE_ONLY_PATTERN.match(trimmed):
        return f"{trimmed} 23:59:59.999"
    return trimmed


def validate_report_datetime(value: str, *, field: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field} is required.")
    if DATE_ONLY_PATTERN.match(trimmed):
        raise ValueError(f"{field} must include time, e.g. 2026-06-03 00:00:00.")
    if not DATETIME_PATTERN.match(trimmed):
        raise ValueError(f"{field} format must be YYYY-MM-DD HH:MM:SS.")
    return trimmed


def format_report_datetime_field(value: str, *, end: bool = False) -> str:
    if end:
        normalized = normalize_date_to(value) or normalize_date_from(value)
    else:
        normalized = normalize_date_from(value)
    if "." in normalized:
        normalized = normalized.split(".", 1)[0]
    return normalized


def validate_report_range(date_from: str, date_to: str) -> tuple[str, str]:
    from_value = normalize_date_from(validate_report_datetime(date_from, field="From"))
    to_value = normalize_date_to(validate_report_datetime(date_to, field="To"))
    if not to_value:
        raise ValueError("To is required.")
    if to_value < from_value:
        raise ValueError("To must be on or after From.")
    return from_value, to_value


def format_report_cell_value(column: str, value: str) -> str:
    if not value:
        return value
    text = value.strip()
    lower = column.lower()
    if "messagedatetime" in lower:
        match = ISO_DATETIME.match(text)
        if match:
            return f"{match.group(3)}.{match.group(2)}.{match.group(1)}{match.group(4)}"
    if "messagedate" in lower:
        match = UNDERSCORE_DATE.match(text)
        if match:
            return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
        match = ISO_DATETIME.match(text)
        if match:
            return f"{match.group(3)}.{match.group(2)}.{match.group(1)}"
    return value


def _strip_sql_string_literals(sql: str) -> str:
    return re.sub(r"'(?:''|[^'])*'", "''", sql)


def validate_custom_sql(sql: str) -> None:
    cleaned = sql.strip()
    while cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    if not cleaned:
        raise ValueError("SQL query is empty.")
    without_strings = _strip_sql_string_literals(cleaned)
    if ";" in without_strings:
        raise ValueError("Only a single SQL statement is allowed.")
    if FORBIDDEN_SQL.search(without_strings):
        raise ValueError("Only SELECT queries are allowed.")
    if FORBIDDEN_FUNCTIONS.search(without_strings):
        raise ValueError(
            "File-access functions (read_csv, read_parquet, glob, ...) are not allowed."
        )
    lowered = without_strings.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("Query must start with SELECT or WITH.")


def run_report_query(
    *,
    mode: str,
    date_from: str | None = None,
    date_to: str | None = None,
    txn_id: str | None = None,
    sql: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> ReportResult:
    from app.services.file_report import run_report_query as run_file_report

    return run_file_report(
        mode=mode,
        date_from=date_from,
        date_to=date_to,
        txn_id=txn_id,
        sql=sql,
        limit=limit,
        offset=offset,
    )
