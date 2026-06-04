from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.paths import get_csv_storage_dir, get_report_output_dir
from app.parsers.models import CSV_COLUMNS
from app.services.report import run_report_query, validate_custom_sql
from tests.conftest import SAMPLE_TXN_ID

client = TestClient(app)


def _write_day_csv(csv_text: str, day: str = "2026-05-27") -> None:
    csv_dir = get_csv_storage_dir()
    path = csv_dir / f"{day}.csv"
    path.write_text(csv_text, encoding="utf-8")


def test_report_by_date_returns_expected_columns(data_dirs, sample_csv_text: str) -> None:
    _write_day_csv(sample_csv_text)
    result = run_report_query(
        mode="date",
        date_from="2026-05-27",
        date_to="2026-05-27",
    )

    assert result.row_count > 0
    assert "areq_messagedatetime" in result.columns
    assert "txn_result" in result.columns
    assert "txn_timeline" in result.columns
    assert "browser_user_agent" in result.columns
    assert list(get_report_output_dir().glob("report-*.csv"))


def test_report_by_txn_id_returns_single_row(data_dirs, sample_csv_text: str) -> None:
    _write_day_csv(sample_csv_text)
    result = run_report_query(mode="txnId", txn_id=SAMPLE_TXN_ID, date_from="2026-05-27", date_to="2026-05-27")

    assert result.row_count == 1
    assert result.rows[0]["threedsservertransid"] == SAMPLE_TXN_ID


def test_report_one_row_per_areq_with_multiple_ares(data_dirs) -> None:
    txn_id = "11111111-1111-4111-8111-111111111111"
    base = {column: "" for column in CSV_COLUMNS}
    base["logFile"] = "test.log"
    base["threeDSServerTransID"] = txn_id
    base["messageDateTime"] = "2026-05-27 10:00:00.000"
    base["acctNumber"] = "516812****0000"
    rows = [
        {**base, "messageType": "AReq"},
        {**base, "messageType": "ARes", "transStatus": "C", "messageDateTime": "2026-05-27 10:00:01.000"},
        {**base, "messageType": "ARes", "transStatus": "N", "messageDateTime": "2026-05-27 10:00:02.000"},
        {**base, "messageType": "ARes", "transStatus": "Y", "messageDateTime": "2026-05-27 10:00:03.000"},
        {**base, "messageType": "ARes", "transStatus": "R", "messageDateTime": "2026-05-27 10:00:04.000"},
    ]
    _write_day_csv(
        "\n".join(
            [
                ";".join(CSV_COLUMNS),
                *[ ";".join(row.get(column, "") for column in CSV_COLUMNS) for row in rows ],
            ]
        )
        + "\n"
    )
    result = run_report_query(mode="txnId", txn_id=txn_id, date_from="2026-05-27", date_to="2026-05-27")
    assert result.row_count == 1
    assert result.rows[0]["ares_status"] == "ARES: R+NULL"


def test_report_custom_accepts_date_range_with_missing_csv_days(data_dirs, sample_csv_text: str) -> None:
    _write_day_csv(sample_csv_text, day="2026-05-27")
    _write_day_csv(sample_csv_text, day="2026-06-03")
    result = run_report_query(
        mode="date",
        date_from="2026-05-27",
        date_to="2026-06-03",
    )
    assert "areq_messagedatetime" in result.columns


def test_custom_sql_allows_trailing_semicolon() -> None:
    validate_custom_sql("WITH x AS (SELECT 1 AS n) SELECT n FROM x;")


def test_custom_sql_rejects_drop(data_dirs, sample_csv_text: str) -> None:
    _write_day_csv(sample_csv_text)
    response = client.post(
        "/api/report/run",
        json={"mode": "custom", "sql": "DROP TABLE cust_acs_3dsmess"},
    )
    assert response.status_code == 400
