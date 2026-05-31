from __future__ import annotations

from pathlib import Path

import pytest

from app.services.log_storage import (
    delete_log_file,
    list_log_days,
    list_log_files,
    read_log_files_by_ids,
    save_upload,
)

ACS1_NAME = "ACS1_common.2026-05-24.0.log"
ACS2_NAME = "ACS2_common.2026-05-24.0.log"


@pytest.fixture
def log_storage_setup(database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_STORAGE_DIR", str(tmp_path))
    schema_sql = Path(__file__).resolve().parents[1] / "db" / "init" / "02_log_files.sql"

    import psycopg

    with psycopg.connect(database_url) as connection:
        connection.execute(schema_sql.read_text(encoding="utf-8"))
        connection.execute("GRANT SELECT ON log_file TO vst_readonly")
        connection.execute("TRUNCATE log_file RESTART IDENTITY")
        connection.commit()


def test_save_upload_and_list_days(log_storage_setup: None) -> None:
    save_upload(ACS1_NAME, b"acs1-content")
    save_upload(ACS2_NAME, b"acs2-content")

    days = list_log_days()
    assert len(days) == 1
    assert days[0]["date"] == "2026-05-24"
    assert days[0]["acs1"] is True
    assert days[0]["acs2"] is True
    assert days[0]["complete"] is True

    files = list_log_files("2026-05-24")
    assert len(files) == 2
    assert {file["acsNode"] for file in files} == {"acs1", "acs2"}


def test_replace_same_day_and_node(log_storage_setup: None) -> None:
    first = save_upload(ACS1_NAME, b"first")
    second = save_upload(ACS1_NAME, b"second")

    assert first["id"] == second["id"]
    assert second["fileSize"] == len(b"second")

    stored = read_log_files_by_ids([second["id"]])
    assert stored[0][1] == "second"


def test_incomplete_day_inventory(log_storage_setup: None) -> None:
    save_upload(ACS1_NAME, b"acs1-only")

    days = list_log_days()
    assert days[0]["acs1"] is True
    assert days[0]["acs2"] is False
    assert days[0]["complete"] is False


def test_read_and_delete_log_file(log_storage_setup: None) -> None:
    saved = save_upload(ACS1_NAME, b"content")
    stored = read_log_files_by_ids([saved["id"]])
    assert stored[0][0] == ACS1_NAME

    delete_log_file(saved["id"])
    assert list_log_files("2026-05-24") == []


def test_read_missing_file_id(log_storage_setup: None) -> None:
    with pytest.raises(ValueError, match="not found"):
        read_log_files_by_ids([9999])
