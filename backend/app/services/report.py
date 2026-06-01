from __future__ import annotations

import re
from dataclasses import dataclass

DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FORBIDDEN_SQL = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY)\b",
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


def validate_custom_sql(sql: str) -> None:
    cleaned = sql.strip().rstrip(";")
    if not cleaned:
        raise ValueError("SQL query is empty.")
    if ";" in cleaned:
        raise ValueError("Only a single SQL statement is allowed.")
    if FORBIDDEN_SQL.search(cleaned):
        raise ValueError("Only SELECT queries are allowed.")
    lowered = cleaned.lower()
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
