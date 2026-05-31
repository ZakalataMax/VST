from __future__ import annotations

import re
from dataclasses import dataclass

from app.db import get_connection, load_report_query_sql

DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}")
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


def _wrap_with_pagination(sql: str, limit: int, offset: int) -> str:
    cleaned = sql.strip().rstrip(";")
    return f"SELECT * FROM ({cleaned}) AS report_query LIMIT {limit} OFFSET {offset}"


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
    limit = min(max(limit, 1), MAX_LIMIT)
    offset = max(offset, 0)

    if mode == "custom":
        if not sql:
            raise ValueError("Custom mode requires sql.")
        validate_custom_sql(sql)
        query = _wrap_with_pagination(sql, limit, offset)
        readonly = True
        params: dict | tuple = ()
    elif mode == "txnId":
        if not txn_id or not txn_id.strip():
            raise ValueError("Transaction ID is required.")
        query = _wrap_with_pagination(load_report_query_sql(), limit, offset)
        readonly = False
        params = {
            "date_from": normalize_date_from(date_from or "1970-01-01"),
            "date_to": normalize_date_to(date_to),
            "txn_id": txn_id.strip(),
        }
    elif mode == "date":
        if not date_from or not date_from.strip():
            raise ValueError("dateFrom is required.")
        query = _wrap_with_pagination(load_report_query_sql(), limit, offset)
        readonly = False
        params = {
            "date_from": normalize_date_from(date_from),
            "date_to": normalize_date_to(date_to),
            "txn_id": None,
        }
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    with get_connection(readonly=readonly) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            fetched = cursor.fetchall()

    columns = list(fetched[0].keys()) if fetched else []
    rows = [{key: ("" if value is None else str(value)) for key, value in row.items()} for row in fetched]
    return ReportResult(columns=columns, rows=rows, row_count=len(rows), limit=limit, offset=offset)
