from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import duckdb

from app.parsers.csv_writer import dict_rows_to_csv, save_dict_rows_csv
from app.paths import get_report_output_dir, load_report_query_sql
from app.services.csv_storage import CSV_TO_DB, list_all_csv_paths, resolve_csv_paths_for_dates
from app.services.report import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    ReportResult,
    normalize_date_from,
    normalize_date_to,
    validate_custom_sql,
)

DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _iter_dates(date_from: str, date_to: str | None) -> list[str]:
    start = date.fromisoformat(date_from[:10])
    end = date.fromisoformat((date_to or date_from)[:10])
    if end < start:
        raise ValueError("dateTo must be on or after dateFrom.")

    dates: list[str] = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _duckdb_view_sql(csv_paths: list[Path]) -> str:
    paths_literal = ", ".join(f"'{path.as_posix()}'" for path in csv_paths)
    select_columns = ",\n        ".join(
        f'"{csv_col}" AS {db_col}' for csv_col, db_col in CSV_TO_DB.items()
    )
    return f"""
        CREATE OR REPLACE VIEW cust_acs_3dsmess AS
        SELECT
            {select_columns}
        FROM read_csv([{paths_literal}], header=true, union_by_name=true, all_varchar=true)
    """


def _adapt_report_sql_for_duckdb(sql: str) -> str:
    adapted = sql.replace("%%", "%")
    adapted = adapted.replace("%(txn_id)s::text IS NULL", "(? IS NULL)")
    adapted = adapted.replace("areq.threedsservertransid = %(txn_id)s::text", "areq.threedsservertransid = ?")
    adapted = adapted.replace("areq.messagedatetime >= %(date_from)s::text", "areq.messagedatetime >= ?")
    adapted = adapted.replace(
        "(%(date_to)s::text IS NULL OR areq.messagedatetime <= %(date_to)s::text)",
        "(? IS NULL OR areq.messagedatetime <= ?)",
    )
    return adapted


def _report_params(date_from: str, date_to: str | None, txn_id: str | None) -> tuple:
    return (
        txn_id,
        txn_id,
        date_from,
        date_to,
        date_to,
    )


def _build_report_output_name(
    *,
    mode: str,
    date_from: str | None,
    date_to: str | None,
    txn_id: str | None,
) -> str:
    if mode == "txnId" and txn_id:
        safe_txn = re.sub(r"[^0-9a-fA-F-]", "", txn_id.strip())
        return f"report-txn-{safe_txn}.csv"
    from_day = (date_from or "unknown")[:10]
    to_day = (date_to or date_from or from_day)[:10]
    if from_day == to_day:
        return f"report-{from_day}.csv"
    return f"report-{from_day}-to-{to_day}.csv"


def _save_report_csv(columns: list[str], rows: list[dict], output_path: Path) -> None:
    save_dict_rows_csv(output_path, columns, rows)


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
        if date_from and date_from.strip():
            csv_paths = resolve_csv_paths_for_dates(_iter_dates(date_from, date_to))
        else:
            csv_paths = list_all_csv_paths()
        report_sql = sql.strip().rstrip(";")
        params: tuple = ()
    elif mode == "txnId":
        if not txn_id or not txn_id.strip():
            raise ValueError("Transaction ID is required.")
        normalized_from = normalize_date_from(date_from or "1970-01-01")
        normalized_to = normalize_date_to(date_to)
        if date_from and date_from.strip():
            csv_paths = resolve_csv_paths_for_dates(
                _iter_dates(normalized_from[:10], normalized_to[:10] if normalized_to else normalized_from[:10])
            )
        else:
            csv_paths = list_all_csv_paths()
        report_sql = _adapt_report_sql_for_duckdb(load_report_query_sql())
        params = _report_params(normalized_from, normalized_to, txn_id.strip())
    elif mode == "date":
        if not date_from or not date_from.strip():
            raise ValueError("dateFrom is required.")
        normalized_from = normalize_date_from(date_from)
        normalized_to = normalize_date_to(date_to)
        csv_paths = resolve_csv_paths_for_dates(
            _iter_dates(normalized_from[:10], normalized_to[:10] if normalized_to else normalized_from[:10])
        )
        report_sql = _adapt_report_sql_for_duckdb(load_report_query_sql())
        params = _report_params(normalized_from, normalized_to, None)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    connection = duckdb.connect()
    try:
        connection.execute(_duckdb_view_sql(csv_paths))
        connection.execute(f"CREATE TEMP TABLE report_result AS {report_sql}", params)
        columns = [
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'report_result' ORDER BY ordinal_position"
            ).fetchall()
        ]
        total = connection.execute("SELECT COUNT(*) FROM report_result").fetchone()[0]

        all_rows_raw = connection.execute("SELECT * FROM report_result ORDER BY 1").fetchall()
        all_rows = [
            {col: ("" if value is None else str(value)) for col, value in zip(columns, row)}
            for row in all_rows_raw
        ]

        output_name = _build_report_output_name(
            mode=mode,
            date_from=date_from,
            date_to=date_to,
            txn_id=txn_id,
        )
        output_path = get_report_output_dir() / output_name
        _save_report_csv(columns, all_rows, output_path)

        page_rows = all_rows[offset : offset + limit]
        return ReportResult(
            columns=columns,
            rows=page_rows,
            row_count=total,
            limit=limit,
            offset=offset,
        )
    finally:
        connection.close()
