from __future__ import annotations

from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
REFERENCE_CSV = SAMPLES_DIR / "3ds-messages-acs1-acs2-2026-05-27-to-2026-05-29-spec-aligned.csv"
SAMPLE_TXN_ID = "abd28639-24f2-49aa-9e1b-541391c4d5b3"


@pytest.fixture
def data_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    logs_dir = tmp_path / "logs"
    csv_dir = tmp_path / "csv"
    reports_dir = tmp_path / "csv_reports_final"
    logs_dir.mkdir()
    csv_dir.mkdir()
    reports_dir.mkdir()
    monkeypatch.setenv("LOG_STORAGE_DIR", str(logs_dir))
    monkeypatch.setenv("CSV_STORAGE_DIR", str(csv_dir))
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(reports_dir))
    return tmp_path


@pytest.fixture
def sample_csv_text() -> str:
    if not REFERENCE_CSV.exists():
        pytest.skip("Reference CSV sample is missing.")
    import csv
    import io

    from app.parsers.csv_writer import CSV_DELIMITER

    with REFERENCE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        day_rows = [
            row
            for row in reader
            if row.get("messageDateTime", "").startswith("2026-05-27")
        ][:2000]

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=CSV_DELIMITER,
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(day_rows)
    return output.getvalue()
