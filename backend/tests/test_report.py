from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.csv_import import import_csv_text
from app.services.report import run_report_query
from tests.conftest import SAMPLE_TXN_ID

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_table(reset_table) -> None:
    return None


def test_report_by_date_returns_expected_columns(sample_csv_text: str) -> None:
    import_csv_text(sample_csv_text)
    result = run_report_query(
        mode="date",
        date_from="2026-05-27",
        date_to="2026-05-27",
    )

    assert result.row_count > 0
    assert "areq_messagedatetime" in result.columns
    assert "txn_result" in result.columns
    assert "txn_timeline" in result.columns


def test_report_by_txn_id_returns_single_row(sample_csv_text: str) -> None:
    import_csv_text(sample_csv_text)
    result = run_report_query(mode="txnId", txn_id=SAMPLE_TXN_ID)

    assert result.row_count == 1
    assert result.rows[0]["threedsservertransid"] == SAMPLE_TXN_ID


def test_custom_sql_rejects_drop() -> None:
    response = client.post(
        "/api/report/run",
        json={"mode": "custom", "sql": "DROP TABLE cust_acs_3dsmess"},
    )
    assert response.status_code == 400
