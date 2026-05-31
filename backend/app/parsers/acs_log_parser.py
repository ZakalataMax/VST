from __future__ import annotations

import json
import re
from pathlib import Path
from typing import BinaryIO, TextIO

from app.parsers.field_mapping import apply_json_payload
from app.parsers.models import MESSAGE_SORT_ORDER, MessageRow, ParseStats
from app.parsers.patterns import (
    AUTH_METHOD_SWITCH_RE,
    CHALLENGE_ANSWER_RE,
    CHALLENGE_EXPIRING_RE,
    CHALLENGE_METHOD_RE,
    CHALLENGE_NOT_ACCEPTED_RE,
    CHALLENGE_SUCCEEDED_RE,
    CREQ_STARTED_RE,
    INCOMING_MESSAGE_PAYLOAD_RE,
    KV_PAIR_RE,
    OOB_INIT_IN_RE,
    OOB_INIT_OUT_RE,
    OOB_RESULT_IN_RE,
    OOB_RESULT_OUT_RE,
    OUTGOING_MESSAGE_PAYLOAD_RE,
    TIMESTAMP_RE,
)

SKIP_JSON_MESSAGE_TYPES: set[str] = set()


def _base_row(log_file: str, timestamp: str, source_index: int) -> MessageRow:
    return MessageRow(
        log_file=log_file,
        message_datetime=timestamp,
        message_type="",
        source_index=source_index,
    )


def _parse_kv_pairs(text: str) -> dict[str, str]:
    return {key: value.strip() for key, value in KV_PAIR_RE.findall(text)}


def _parse_json_array_payload(raw: str) -> list[dict]:
    stripped = raw.strip()
    if not stripped.startswith("{") and not stripped.startswith("["):
        return []
    normalized = stripped if stripped.startswith("[") else f"[{stripped}]"
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _parse_json_object_payload(raw: str) -> dict | None:
    data = json.loads(raw)
    return data if isinstance(data, dict) else None


def _rows_from_json_array(
    log_file: str,
    timestamp: str,
    direction: str,
    raw_json: str,
    source_index: int,
) -> list[MessageRow]:
    rows: list[MessageRow] = []
    for payload in _parse_json_array_payload(raw_json):
        message_type = payload.get("messageType")
        if message_type in SKIP_JSON_MESSAGE_TYPES:
            continue
        row = _base_row(log_file, timestamp, source_index)
        row.message_direction = direction
        apply_json_payload(row, payload)
        if row.message_type == "CReq":
            if direction != "In":
                continue
            row.creq_incoming = "true"
        if row.message_type:
            rows.append(row)
    return rows


def _row_from_oob_message(
    log_file: str,
    timestamp: str,
    direction: str,
    message_type: str,
    raw_json: str,
    source_index: int,
) -> MessageRow | None:
    payload = _parse_json_object_payload(raw_json)
    if not payload:
        return None
    row = _base_row(log_file, timestamp, source_index)
    row.message_type = message_type
    row.message_direction = direction
    trans_id = payload.get("tdssTxnId") or payload.get("threeDSServerTransID")
    if not trans_id:
        return None
    row.three_ds_server_trans_id = str(trans_id)
    if message_type == "OobResultRequest":
        if payload.get("status") is not None:
            row.oob_result_status = str(payload["status"])
        if payload.get("method") is not None:
            row.oob_result_method = str(payload["method"])
    return row


def _parse_line(log_file: str, line: str, source_index: int) -> list[MessageRow]:
    timestamp_match = TIMESTAMP_RE.match(line)
    if not timestamp_match:
        return []
    timestamp = timestamp_match.group(1)

    creq_match = CREQ_STARTED_RE.search(line)
    if creq_match:
        return []

    challenge_method_match = CHALLENGE_METHOD_RE.search(line)
    if challenge_method_match:
        row = _base_row(log_file, timestamp, source_index)
        row.message_type = "ChallengeMethod"
        row.three_ds_server_trans_id = challenge_method_match.group(1)
        row.challenge_method = challenge_method_match.group(2)
        row.challenge_method_code = challenge_method_match.group(3)
        return [row]

    challenge_answer_match = CHALLENGE_ANSWER_RE.search(line)
    if challenge_answer_match:
        pairs = _parse_kv_pairs(challenge_answer_match.group(1))
        if "submit" not in pairs:
            return []
        row = _base_row(log_file, timestamp, source_index)
        row.message_type = "ChallengeAnswer"
        row.message_direction = "In"
        row.three_ds_server_trans_id = pairs.get("acs_ops_data", "")
        row.challenge_submit = pairs.get("submit", "")
        return [row]

    challenge_succeeded_match = CHALLENGE_SUCCEEDED_RE.search(line)
    if challenge_succeeded_match:
        row = _base_row(log_file, timestamp, source_index)
        row.message_type = "ChallengeOutcome"
        row.three_ds_server_trans_id = challenge_succeeded_match.group(1)
        row.is_challenge_succeeded = "true"
        return [row]

    challenge_not_accepted_match = CHALLENGE_NOT_ACCEPTED_RE.search(line)
    if challenge_not_accepted_match:
        row = _base_row(log_file, timestamp, source_index)
        row.message_type = "ChallengeOutcome"
        row.three_ds_server_trans_id = challenge_not_accepted_match.group(1)
        row.is_challenge_succeeded = "false"
        return [row]

    challenge_expiring_match = CHALLENGE_EXPIRING_RE.search(line)
    if challenge_expiring_match:
        row = _base_row(log_file, timestamp, source_index)
        row.message_type = "ChallengeExpiring"
        row.three_ds_server_trans_id = challenge_expiring_match.group(1)
        row.is_challenge_expired = "true"
        return [row]

    auth_switch_match = AUTH_METHOD_SWITCH_RE.search(line)
    if auth_switch_match:
        row = _base_row(log_file, timestamp, source_index)
        row.message_type = "AuthMethodSwitch"
        row.three_ds_server_trans_id = auth_switch_match.group(1)
        row.auth_method_switch = f"{auth_switch_match.group(2)}->{auth_switch_match.group(3)}"
        return [row]

    for regex, direction, message_type in (
        (OOB_INIT_OUT_RE, "Out", "OobInitRequest"),
        (OOB_INIT_IN_RE, "In", "OobInitResponse"),
        (OOB_RESULT_IN_RE, "In", "OobResultRequest"),
        (OOB_RESULT_OUT_RE, "Out", "OobResultResponse"),
    ):
        match = regex.search(line)
        if match:
            row = _row_from_oob_message(
                log_file,
                timestamp,
                direction,
                message_type,
                match.group(2),
                source_index,
            )
            return [row] if row else []

    incoming_payload_match = INCOMING_MESSAGE_PAYLOAD_RE.search(line)
    if incoming_payload_match:
        payload_text = incoming_payload_match.group(1)
        if not payload_text.startswith(("OobInit", "OobResult", "ChallengeAnswerRequest")):
            return _rows_from_json_array(
                log_file,
                timestamp,
                "In",
                payload_text,
                source_index,
            )

    outgoing_payload_match = OUTGOING_MESSAGE_PAYLOAD_RE.search(line)
    if outgoing_payload_match:
        payload_text = outgoing_payload_match.group(1)
        if not payload_text.startswith(("OobInit", "OobResult")):
            return _rows_from_json_array(
                log_file,
                timestamp,
                "Out",
                payload_text,
                source_index,
            )

    return []


def parse_log_content(log_file: str, content: str, file_index: int = 0) -> list[MessageRow]:
    rows: list[MessageRow] = []
    for line_no, line in enumerate(content.splitlines()):
        source_index = file_index * 10_000_000 + line_no
        rows.extend(_parse_line(log_file, line, source_index))
    return rows


def parse_log_file(path: str | Path, log_file: str | None = None) -> list[MessageRow]:
    file_path = Path(path)
    display_name = log_file or file_path.name
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    return parse_log_content(display_name, content)


def parse_log_files(files: list[tuple[str, str]], sort_output: bool = True) -> list[MessageRow]:
    all_rows: list[MessageRow] = []
    for file_index, (log_file, content) in enumerate(files):
        all_rows.extend(parse_log_content(log_file, content, file_index))
    if sort_output:
        all_rows.sort(
            key=lambda row: (
                row.message_datetime,
                MESSAGE_SORT_ORDER.get(row.message_type, 999),
                row.source_index,
            )
        )
    return all_rows


def build_output_file_name(
    rows: list[MessageRow],
    source_filenames: list[str] | None = None,
) -> str:
    filename_dates: list[str] = []
    if source_filenames:
        for filename in source_filenames:
            filename_dates.extend(re.findall(r"(\d{4}-\d{2}-\d{2})", filename))
    filename_dates = sorted(set(filename_dates))

    if filename_dates:
        min_date = filename_dates[0]
        max_date = filename_dates[-1]
    else:
        row_dates = sorted(
            {row.message_datetime[:10] for row in rows if len(row.message_datetime) >= 10}
        )
        if not row_dates:
            return "3ds-messages-parser.csv"
        min_date = row_dates[0]
        max_date = row_dates[-1]

    prefix = "3ds-messages"
    if min_date == max_date:
        return f"{prefix}-{min_date}-parser.csv"
    return f"{prefix}-{min_date}-to-{max_date}-parser.csv"


def _detect_acs_node(filename: str) -> str | None:
    lowered = filename.lower()
    if "acs1" in lowered:
        return "acs1"
    if "acs2" in lowered:
        return "acs2"
    return None


def validate_acs_file_names(filenames: list[str]) -> None:
    if not filenames:
        raise ValueError("No log files uploaded.")

    by_date: dict[str, set[str]] = {}
    for filename in filenames:
        node = _detect_acs_node(filename)
        if not node:
            raise ValueError(f"Log file name must include ACS1 or ACS2: {filename}")

        dates = re.findall(r"(\d{4}-\d{2}-\d{2})", filename)
        if not dates:
            raise ValueError(f"Cannot detect date in log file name: {filename}")

        date = dates[0]
        by_date.setdefault(date, set()).add(node)

    missing_pairs = [
        date
        for date, nodes in sorted(by_date.items())
        if nodes != {"acs1", "acs2"}
    ]
    if missing_pairs:
        raise ValueError(
            "Each date must include both ACS1 and ACS2 logs. "
            f"Missing pair for: {', '.join(missing_pairs)}"
        )


def build_stats(rows: list[MessageRow]) -> ParseStats:
    stats = ParseStats()
    stats.total_rows = len(rows)
    for row in rows:
        stats.by_message_type[row.message_type] = stats.by_message_type.get(row.message_type, 0) + 1
    return stats


def read_uploaded_files(uploads: list[tuple[str, bytes | BinaryIO | TextIO]]) -> list[tuple[str, str]]:
    parsed_files: list[tuple[str, str]] = []
    for filename, handle in uploads:
        if isinstance(handle, bytes):
            content = handle.decode("utf-8", errors="ignore")
        else:
            raw = handle.read()
            content = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
        parsed_files.append((filename, content))
    return parsed_files
