from __future__ import annotations

from pathlib import Path

import pytest

from app.parsers.acs_log_parser import parse_log_files
from app.parsers.csv_writer import rows_to_csv
from app.services.csv_import import import_csv_text
from app.services.report import run_report_query
from tests.conftest import SAMPLE_TXN_ID

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
SAMPLE_LOGS = sorted(SAMPLES_DIR.glob("ACS*_common.2026-05-*.log"))


@pytest.fixture(autouse=True)
def _reset_table(reset_table) -> None:
    return None


@pytest.mark.skipif(not SAMPLE_LOGS, reason="Sample log files are not available")
def test_parser_import_report_pipeline() -> None:
    files = [(path.name, path.read_text(encoding="utf-8", errors="ignore")) for path in SAMPLE_LOGS]
    rows = parse_log_files(files)
    import_csv_text(rows_to_csv(rows))

    result = run_report_query(mode="txnId", txn_id=SAMPLE_TXN_ID)
    assert result.row_count == 1

    row = result.rows[0]
    assert row.get("threedsservertransid") == SAMPLE_TXN_ID
    assert row.get("txn_timeline")
    assert row.get("areq_messagedate")
