from __future__ import annotations

from app.common.report_utils import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    ReportResult,
    format_report_cell_value,
    format_report_datetime_field,
    normalize_date_from,
    normalize_date_to,
    validate_custom_sql,
    validate_report_datetime,
    validate_report_range,
)

__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "ReportResult",
    "format_report_cell_value",
    "format_report_datetime_field",
    "normalize_date_from",
    "normalize_date_to",
    "validate_custom_sql",
    "validate_report_datetime",
    "validate_report_range",
    "run_report_query",
]


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
    from app.acs.services.file_report import run_report_query as run_file_report

    return run_file_report(
        mode=mode,
        date_from=date_from,
        date_to=date_to,
        txn_id=txn_id,
        sql=sql,
        limit=limit,
        offset=offset,
    )
