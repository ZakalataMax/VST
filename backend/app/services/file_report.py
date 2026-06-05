from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb

from app.parsers.csv_writer import CSV_DELIMITER, duckdb_read_csv_delim, save_dict_rows_csv
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
SQL_FILTER_DATE_PATTERN = re.compile(
    r"areq\.messagedatetime\s*>=\s*'(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _iter_dates(date_from: str, date_to: str | None) -> list[str]:
    from_day = normalize_date_from(date_from)[:10]
    to_day = normalize_date_to(date_to or date_from)[:10] if date_to or date_from else from_day
    start = date.fromisoformat(from_day)
    end = date.fromisoformat(to_day)
    if end < start:
        raise ValueError("dateTo must be on or after dateFrom.")

    dates: list[str] = []
    current = start
    while current <= end:
        dates.append(current.isoformat())
        current += timedelta(days=1)
    return dates


def _extract_sql_filter_dates(sql: str) -> list[str]:
    return sorted({match.group(1) for match in SQL_FILTER_DATE_PATTERN.finditer(sql)})


def _resolve_csv_paths_for_report(
    *,
    mode: str,
    date_from: str | None,
    date_to: str | None,
    sql: str | None,
) -> list[Path]:
    dates: list[str] = []
    if date_from and date_from.strip():
        dates = _iter_dates(date_from, date_to)

    if mode == "custom" and sql:
        sql_dates = _extract_sql_filter_dates(sql)
        if sql_dates:
            dates = sorted(set(dates) | set(sql_dates))

    if dates:
        return resolve_csv_paths_for_dates(dates)
    return list_all_csv_paths()


def _csv_header_columns(csv_paths: list[Path]) -> set[str]:
    if not csv_paths:
        return set()
    with csv_paths[0].open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=CSV_DELIMITER)
        return set(next(reader, []))


def _duckdb_view_sql(csv_paths: list[Path]) -> str:
    paths_literal = ", ".join(f"'{path.as_posix()}'" for path in csv_paths)
    available = _csv_header_columns(csv_paths)
    select_columns = ",\n        ".join(
        f'"{csv_col}" AS {db_col}'
        if csv_col in available
        else f"NULL::VARCHAR AS {db_col}"
        for csv_col, db_col in CSV_TO_DB.items()
    )
    return f"""
        CREATE OR REPLACE VIEW cust_acs_3dsmess AS
        SELECT
            {select_columns}
        FROM read_csv([{paths_literal}], header=true, delim='{duckdb_read_csv_delim()}', union_by_name=true, all_varchar=true)
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


@dataclass
class ReportExportResult:
    columns: list[str]
    row_count: int
    file_name: str
    output_path: Path


def _resolve_report_query(
    *,
    mode: str,
    date_from: str | None,
    date_to: str | None,
    txn_id: str | None,
    sql: str | None,
) -> tuple[list[Path], str, tuple]:
    if mode == "custom":
        if not sql:
            raise ValueError("Custom mode requires sql.")
        validate_custom_sql(sql)
        csv_paths = _resolve_csv_paths_for_report(
            mode=mode,
            date_from=date_from,
            date_to=date_to,
            sql=sql,
        )
        report_sql = sql.strip().rstrip(";")
        params: tuple = ()
    elif mode == "txnId":
        if not txn_id or not txn_id.strip():
            raise ValueError("Transaction ID is required.")
        normalized_from = normalize_date_from(date_from or "1970-01-01")
        normalized_to = normalize_date_to(date_to)
        csv_paths = _resolve_csv_paths_for_report(
            mode=mode,
            date_from=normalized_from if date_from and date_from.strip() else None,
            date_to=normalized_to,
            sql=None,
        )
        report_sql = _adapt_report_sql_for_duckdb(load_report_query_sql())
        params = _report_params(normalized_from, normalized_to, txn_id.strip())
    elif mode == "date":
        if not date_from or not date_from.strip():
            raise ValueError("dateFrom is required.")
        normalized_from = normalize_date_from(date_from)
        normalized_to = normalize_date_to(date_to)
        csv_paths = _resolve_csv_paths_for_report(
            mode=mode,
            date_from=normalized_from,
            date_to=normalized_to,
            sql=None,
        )
        report_sql = _adapt_report_sql_for_duckdb(load_report_query_sql())
        params = _report_params(normalized_from, normalized_to, None)
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    return csv_paths, report_sql, params


def _load_report_result(
    connection: duckdb.DuckDBPyConnection,
    csv_paths: list[Path],
    report_sql: str,
    params: tuple,
) -> list[str]:
    connection.execute(_duckdb_view_sql(csv_paths))
    connection.execute(f"CREATE TEMP TABLE report_result AS {report_sql}", params)
    return [
        row[0]
        for row in connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'report_result' ORDER BY ordinal_position"
        ).fetchall()
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
    limit = min(max(limit, 1), MAX_LIMIT)
    offset = max(offset, 0)

    csv_paths, report_sql, params = _resolve_report_query(
        mode=mode,
        date_from=date_from,
        date_to=date_to,
        txn_id=txn_id,
        sql=sql,
    )

    connection = duckdb.connect()
    try:
        columns = _load_report_result(connection, csv_paths, report_sql, params)
        total = connection.execute("SELECT COUNT(*) FROM report_result").fetchone()[0]
        page_rows_raw = connection.execute(
            "SELECT * FROM report_result ORDER BY 1 LIMIT ? OFFSET ?",
            [limit, offset],
        ).fetchall()
        page_rows = [
            {col: ("" if value is None else str(value)) for col, value in zip(columns, row)}
            for row in page_rows_raw
        ]
        return ReportResult(
            columns=columns,
            rows=page_rows,
            row_count=total,
            limit=limit,
            offset=offset,
        )
    finally:
        connection.close()


def export_report_csv(
    *,
    mode: str,
    date_from: str | None = None,
    date_to: str | None = None,
    txn_id: str | None = None,
    sql: str | None = None,
) -> ReportExportResult:
    csv_paths, report_sql, params = _resolve_report_query(
        mode=mode,
        date_from=date_from,
        date_to=date_to,
        txn_id=txn_id,
        sql=sql,
    )
    output_name = _build_report_output_name(
        mode=mode,
        date_from=date_from,
        date_to=date_to,
        txn_id=txn_id,
    )
    output_path = get_report_output_dir() / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect()
    try:
        columns = _load_report_result(connection, csv_paths, report_sql, params)
        total = connection.execute("SELECT COUNT(*) FROM report_result").fetchone()[0]
        delim = duckdb_read_csv_delim()
        connection.execute(
            f"""
            COPY (SELECT * FROM report_result ORDER BY 1)
            TO '{output_path.as_posix()}'
            (HEADER, DELIMITER '{delim}')
            """
        )
        return ReportExportResult(
            columns=columns,
            row_count=total,
            file_name=output_name,
            output_path=output_path,
        )
    finally:
        connection.close()
