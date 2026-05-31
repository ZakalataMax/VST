from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import pytest

from app.parsers.acs_log_parser import (
    build_output_file_name,
    build_stats,
    parse_log_files,
    validate_acs_file_names,
)
from tests.csv_test_utils import COMPARE_COLUMNS, normalize_log_file, row_sort_key

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
REFERENCE_CSV = SAMPLES_DIR / "3ds-messages-acs1-acs2-2026-05-27-to-2026-05-29-spec-aligned.csv"
REFERENCE_DATES = ("2026-05-27", "2026-05-28", "2026-05-29")
SAMPLE_LOGS = sorted(
    path
    for path in SAMPLES_DIR.glob("ACS*_common.2026-05-*.log")
    if any(date in path.name for date in REFERENCE_DATES)
)
SAMPLE_TXN_ID = "abd28639-24f2-49aa-9e1b-541391c4d5b3"
ERRO_TXN_ID = "48ea47a9-f6c2-4b56-ac5f-05ff1964edc4"
OOB_TXN_ID = "29f7a225-de8d-463e-a80e-b6d74f8a1099"
CHALLENGE_TXN_ID = "ed6c24c2-66f8-43cd-b786-8ac8b692a9d8"

SPOT_CHECK_CASES = [
    (SAMPLE_TXN_ID, "2026-05-27"),
    (ERRO_TXN_ID, "2026-05-27"),
    (OOB_TXN_ID, "2026-05-27"),
    (CHALLENGE_TXN_ID, "2026-05-27"),
]


def _load_reference_counts() -> Counter:
    counts: Counter = Counter()
    with REFERENCE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            counts[row["messageType"]] += 1
    return counts


def _load_reference_txn_rows(txn_id: str, day_suffix: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with REFERENCE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["threeDSServerTransID"] != txn_id:
                continue
            if day_suffix not in row["logFile"]:
                continue
            rows.append(row)
    return rows


def _assert_txn_matches_reference(
    parsed_rows: list,
    reference_rows: list[dict[str, str]],
) -> None:
    assert len(parsed_rows) == len(reference_rows)

    parsed_dicts = sorted(
        (row.to_csv_dict() for row in parsed_rows),
        key=row_sort_key,
    )
    reference_sorted = sorted(reference_rows, key=row_sort_key)

    for parsed_dict, reference_row in zip(parsed_dicts, reference_sorted):
        assert normalize_log_file(parsed_dict["logFile"]) == normalize_log_file(reference_row["logFile"])
        for column in COMPARE_COLUMNS:
            assert parsed_dict.get(column, "") == reference_row.get(column, ""), column


@pytest.mark.skipif(not SAMPLE_LOGS, reason="Sample log files are not available")
@pytest.mark.parametrize(("txn_id", "day_suffix"), SPOT_CHECK_CASES)
def test_sample_transaction_matches_reference(txn_id: str, day_suffix: str) -> None:
    files = [
        (path.name, path.read_text(encoding="utf-8", errors="ignore"))
        for path in SAMPLE_LOGS
        if day_suffix in path.name
    ]
    parsed = [
        row
        for row in parse_log_files(files)
        if row.three_ds_server_trans_id == txn_id
    ]
    reference = _load_reference_txn_rows(txn_id, day_suffix)
    _assert_txn_matches_reference(parsed, reference)


@pytest.mark.skipif(not SAMPLE_LOGS, reason="Sample log files are not available")
def test_build_output_file_name_uses_min_max_dates() -> None:
    files = [(path.name, path.read_text(encoding="utf-8", errors="ignore")) for path in SAMPLE_LOGS]
    rows = parse_log_files(files)
    assert (
        build_output_file_name(rows, [path.name for path in SAMPLE_LOGS])
        == "3ds-messages-2026-05-27-to-2026-05-29-parser.csv"
    )


def test_build_output_file_name_prefers_uploaded_log_dates() -> None:
    rows = parse_log_files(
        [
            (
                "ACS1_common.2026-05-31.0.log",
                "2026-05-31 00:00:00.000 INFO  example - heartbeat",
            )
        ]
    )
    assert (
        build_output_file_name(rows, ["ACS1_common.2026-05-24.0.log", "ACS2_common.2026-05-24.0.log"])
        == "3ds-messages-2026-05-24-parser.csv"
    )


def test_validate_acs_file_names_requires_matching_date_pairs() -> None:
    with pytest.raises(ValueError, match="Missing pair"):
        validate_acs_file_names(["ACS1_common.2026-05-27.0.log"])
    with pytest.raises(ValueError, match="Missing pair"):
        validate_acs_file_names(
            ["ACS1_common.2026-05-24.0.log", "ACS2_common.2026-05-23.0.log"]
        )
    validate_acs_file_names(
        ["ACS1_common.2026-05-27.0.log", "ACS2_common.2026-05-27.0.log"]
    )
    validate_acs_file_names(
        [
            "ACS1_common.2026-05-23.0.log",
            "ACS2_common.2026-05-23.0.log",
            "ACS1_common.2026-05-24.0.log",
            "ACS2_common.2026-05-24.0.log",
        ]
    )


@pytest.mark.skipif(not SAMPLE_LOGS, reason="Sample log files are not available")
def test_all_sample_logs_match_reference_counts() -> None:
    files = [(path.name, path.read_text(encoding="utf-8", errors="ignore")) for path in SAMPLE_LOGS]
    stats = build_stats(parse_log_files(files))
    reference_counts = _load_reference_counts()

    assert stats.total_rows == sum(reference_counts.values())

    for message_type, expected_count in reference_counts.items():
        assert stats.by_message_type.get(message_type, 0) == expected_count, message_type
