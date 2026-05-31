from __future__ import annotations

import pytest

from app.services.csv_import import get_db_days, get_db_status, import_csv_text


@pytest.fixture(autouse=True)
def _reset_table(reset_table) -> None:
    return None


def test_import_csv_inserts_rows(sample_csv_text: str) -> None:
    result = import_csv_text(sample_csv_text)
    assert result.inserted_rows == 2000
    assert result.min_date == "2026-05-27"
    assert result.max_date == "2026-05-27"

    status = get_db_status()
    assert status["rowCount"] == 2000
    assert status["minDate"] == "2026-05-27"


def test_import_csv_replaces_same_date_range(sample_csv_text: str) -> None:
    first = import_csv_text(sample_csv_text)
    second = import_csv_text(sample_csv_text)

    assert first.inserted_rows == second.inserted_rows
    assert second.deleted_rows == first.inserted_rows

    status = get_db_status()
    assert status["rowCount"] == 2000


def test_get_db_days_full_and_partial(sample_csv_text: str) -> None:
    import_csv_text(sample_csv_text)
    days = get_db_days()
    assert len(days) == 1
    assert days[0]["date"] == "2026-05-27"
    assert days[0]["rowCount"] == 2000
    assert days[0]["fullDay"] is False
