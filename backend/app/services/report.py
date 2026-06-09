from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d{1,3})?$"
)
ISO_DATETIME = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(.*)$")
UNDERSCORE_DATE = re.compile(r"^(\d{2})_(\d{2})_(\d{4})$")
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


PREFERRED_PIVOT_ROW_FIELDS = ("areq_messagedate", "messagedate")
PREFERRED_PIVOT_COL_FIELDS = ("txn_result", "card_scheme", "ares_status", "final_cres_status")


@dataclass
class PivotTable:
    row_field: str
    col_field: str
    row_labels: list[str]
    col_labels: list[str]
    matrix: list[list[int]]
    row_totals: list[int]
    col_totals: list[int]
    grand_total: int


def pick_report_field(columns: list[str], preferred: tuple[str, ...]) -> str | None:
    lower_map = {column.lower(): column for column in columns}
    for name in preferred:
        if name in lower_map:
            return lower_map[name]
    for column in columns:
        lower = column.lower()
        if any(token in lower for token in preferred):
            return column
    return None


def default_pivot_fields(columns: list[str]) -> tuple[str | None, str | None]:
    return (
        pick_report_field(columns, PREFERRED_PIVOT_ROW_FIELDS),
        pick_report_field(columns, PREFERRED_PIVOT_COL_FIELDS),
    )


def _pivot_label(column: str, value: str) -> str:
    text = value.strip()
    if not text:
        return "(empty)"
    return format_report_cell_value(column, text)


def _sort_pivot_row_label(label: str):
    match = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", label)
    if match:
        return (0, int(match.group(3)), int(match.group(2)), int(match.group(1)))
    return (1, label)


def build_count_pivot(
    *,
    row_field: str,
    col_field: str,
    rows: list[tuple[str | None, str | None, int]],
) -> PivotTable:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for raw_row, raw_col, amount in rows:
        row_label = _pivot_label(row_field, "" if raw_row is None else str(raw_row))
        col_label = _pivot_label(col_field, "" if raw_col is None else str(raw_col))
        counts[(row_label, col_label)] += amount

    col_labels = sorted({col for _, col in counts})
    row_labels = sorted({row for row, _ in counts}, key=_sort_pivot_row_label)
    matrix = [[counts.get((row, col), 0) for col in col_labels] for row in row_labels]
    row_totals = [sum(row_values) for row_values in matrix]
    col_totals = [sum(matrix[row_index][col_index] for row_index in range(len(matrix))) for col_index in range(len(col_labels))]
    grand_total = sum(row_totals)
    return PivotTable(
        row_field=row_field,
        col_field=col_field,
        row_labels=row_labels,
        col_labels=col_labels,
        matrix=matrix,
        row_totals=row_totals,
        col_totals=col_totals,
        grand_total=grand_total,
    )


def pivot_table_to_rows(pivot: PivotTable) -> tuple[list[str], list[list[str | int]]]:
    headers = [pivot.row_field, *pivot.col_labels, "Total"]
    body: list[list[str | int]] = []
    for row_index, row_label in enumerate(pivot.row_labels):
        body.append(
            [row_label, *pivot.matrix[row_index], pivot.row_totals[row_index]]
        )
    body.append(["Total", *pivot.col_totals, pivot.grand_total])
    return headers, body


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


def run_report_pivot(
    *,
    mode: str,
    date_from: str | None = None,
    date_to: str | None = None,
    txn_id: str | None = None,
    sql: str | None = None,
    row_field: str | None = None,
    col_field: str | None = None,
) -> PivotTable:
    from app.services.file_report import run_report_pivot as run_file_report_pivot

    return run_file_report_pivot(
        mode=mode,
        date_from=date_from,
        date_to=date_to,
        txn_id=txn_id,
        sql=sql,
        row_field=row_field,
        col_field=col_field,
    )
