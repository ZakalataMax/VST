from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.paths import get_csv_storage_dir, get_report_output_dir
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
    assert list(get_report_output_dir().glob("report-*.csv"))


def test_report_by_txn_id_returns_single_row(data_dirs, sample_csv_text: str) -> None:
    _write_day_csv(sample_csv_text)
    result = run_report_query(mode="txnId", txn_id=SAMPLE_TXN_ID, date_from="2026-05-27", date_to="2026-05-27")

    assert result.row_count == 1
    assert result.rows[0]["threedsservertransid"] == SAMPLE_TXN_ID


def test_custom_sql_allows_trailing_semicolon() -> None:
    validate_custom_sql("WITH x AS (SELECT 1 AS n) SELECT n FROM x;")


def test_custom_sql_rejects_drop(data_dirs, sample_csv_text: str) -> None:
    _write_day_csv(sample_csv_text)
    response = client.post(
        "/api/report/run",
        json={"mode": "custom", "sql": "DROP TABLE cust_acs_3dsmess"},
    )
    assert response.status_code == 400
