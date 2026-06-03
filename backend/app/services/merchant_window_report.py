from __future__ import annotations

import csv
import io
import re
import duckdb

from app.paths import get_report_output_dir, load_report_query_sql
from app.services.csv_storage import resolve_csv_paths_for_dates
from app.services.file_report import (
    _adapt_report_sql_for_duckdb,
    _duckdb_view_sql,
    _report_params,
    _save_report_csv,
)

_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}(:\d{2})?(\.\d{3})?$")


def _normalize_time(value: str) -> str:
    trimmed = value.strip()
    if not _TIME_PATTERN.match(trimmed):
        raise ValueError(f"Invalid time value: {value}")
    if len(trimmed) == 5:
        trimmed = f"{trimmed}:00"
    if "." not in trimmed:
        trimmed = f"{trimmed}.000"
    return trimmed


def _window_bounds(date: str, time_from: str, time_to: str) -> tuple[str, str]:
    day = date.strip()[:10]
    start = _normalize_time(time_from)
    end = _normalize_time(time_to)
    return f"{day} {start}", f"{day} {end}"


def _qualifying_txn_sql(min_attempts: int) -> str:
    return f"""
        WITH window_events AS (
            SELECT *
            FROM cust_acs_3dsmess
            WHERE messagedatetime >= ?
              AND messagedatetime <= ?
        ),
        txn_keys AS (
            SELECT
                threedsservertransid,
                MAX(CASE WHEN messagetype = 'AReq' THEN acctnumber END) AS acctnumber,
                MAX(CASE WHEN messagetype = 'AReq' THEN acquirermerchantid END) AS acquirermerchantid
            FROM window_events
            WHERE threedsservertransid IS NOT NULL AND threedsservertransid <> ''
            GROUP BY threedsservertransid
        ),
        last_cres AS (
            SELECT
                threedsservertransid,
                MAX(messagedatetime) AS final_cres_datetime
            FROM window_events
            WHERE messagetype = 'CRes'
              AND threedsservertransid IS NOT NULL
              AND threedsservertransid <> ''
            GROUP BY threedsservertransid
        ),
        failed_txn AS (
            SELECT DISTINCT e.threedsservertransid
            FROM window_events e
            WHERE e.messagetype IN ('ARes', 'RReq')
              AND (
                UPPER(TRIM(COALESCE(e.transstatus, ''))) = 'N'
                OR TRIM(COALESCE(e.transstatus, '')) = ''
              )
            UNION
            SELECT DISTINCT e.threedsservertransid
            FROM window_events e
            INNER JOIN last_cres lc ON e.threedsservertransid = lc.threedsservertransid
            WHERE e.messagetype = 'CRes'
              AND e.messagedatetime < lc.final_cres_datetime
              AND (
                UPPER(TRIM(COALESCE(e.transstatus, ''))) = 'N'
                OR TRIM(COALESCE(e.transstatus, '')) = ''
              )
        ),
        qualifying_pairs AS (
            SELECT t.acctnumber, t.acquirermerchantid
            FROM failed_txn f
            INNER JOIN txn_keys t ON f.threedsservertransid = t.threedsservertransid
            WHERE t.acctnumber IS NOT NULL AND TRIM(t.acctnumber) <> ''
              AND t.acquirermerchantid IS NOT NULL AND TRIM(t.acquirermerchantid) <> ''
            GROUP BY t.acctnumber, t.acquirermerchantid
            HAVING COUNT(DISTINCT f.threedsservertransid) >= {int(min_attempts)}
        )
        SELECT DISTINCT f.threedsservertransid
        FROM failed_txn f
        INNER JOIN txn_keys t ON f.threedsservertransid = t.threedsservertransid
        INNER JOIN qualifying_pairs q
            ON t.acctnumber = q.acctnumber AND t.acquirermerchantid = q.acquirermerchantid
    """


def run_merchant_window_report(
    *,
    date: str,
    time_from: str = "07:00:00",
    time_to: str = "11:00:00",
    min_attempts: int = 2,
) -> dict:
    if min_attempts < 1:
        raise ValueError("minAttempts must be at least 1.")

    datetime_from, datetime_to = _window_bounds(date, time_from, time_to)
    csv_paths = resolve_csv_paths_for_dates([date[:10]])
    report_sql = _adapt_report_sql_for_duckdb(load_report_query_sql()).rstrip()
    if report_sql.upper().endswith("ORDER BY 1"):
        report_sql = (
            report_sql[:-len("ORDER BY 1")].rstrip()
            + "\n  AND areq.threedsservertransid IN (SELECT threedsservertransid FROM qualifying_txn)\n"
            + "ORDER BY 1"
        )
    else:
        report_sql += (
            "\n  AND areq.threedsservertransid IN (SELECT threedsservertransid FROM qualifying_txn)"
        )
    report_params = _report_params(datetime_from, datetime_to, None)

    connection = duckdb.connect()
    try:
        connection.execute(_duckdb_view_sql(csv_paths))
        connection.execute(
            f"CREATE TEMP TABLE qualifying_txn AS {_qualifying_txn_sql(min_attempts)}",
            [datetime_from, datetime_to],
        )
        txn_count = connection.execute("SELECT COUNT(*) FROM qualifying_txn").fetchone()[0]
        if txn_count == 0:
            raise ValueError(
                "No transactions matched the window test "
                f"({datetime_from} — {datetime_to}, min {min_attempts} attempts per card+merchant)."
            )

        connection.execute(f"CREATE TEMP TABLE report_result AS {report_sql}", report_params)
        columns = [
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'report_result' ORDER BY ordinal_position"
            ).fetchall()
        ]
        all_rows_raw = connection.execute("SELECT * FROM report_result ORDER BY 1").fetchall()
        all_rows = [
            {col: ("" if value is None else str(value)) for col, value in zip(columns, row)}
            for row in all_rows_raw
        ]

        day = date[:10]
        output_name = f"report-merchant-window-{day}-0700-1100.csv"
        output_path = get_report_output_dir() / output_name
        _save_report_csv(columns, all_rows, output_path)

        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

        return {
            "columns": columns,
            "csv": buffer.getvalue(),
            "fileName": output_name,
            "savedPath": str(output_path),
            "rowCount": len(all_rows),
            "qualifyingTxnCount": txn_count,
            "date": day,
            "timeFrom": datetime_from,
            "timeTo": datetime_to,
            "minAttempts": min_attempts,
        }
    finally:
        connection.close()
