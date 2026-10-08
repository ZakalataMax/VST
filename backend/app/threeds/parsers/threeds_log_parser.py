from __future__ import annotations

import json
from pathlib import Path

from app.common.parse_diagnostics import ParseDiagnostics, max_dropped_lines
from app.threeds.parsers.field_mapping import apply_json_payload
from app.threeds.parsers.models import MESSAGE_SORT_ORDER, ThreeDsMessageRow
from app.threeds.parsers.patterns import (
    INCOMING_MESSAGE_PAYLOAD_RE,
    METHOD_EXPIRED_RE,
    OUTGOING_MESSAGE_PAYLOAD_RE,
    RECEIVED_RREQ_STATUS_RE,
    TIMESTAMP_RE,
)

__all__ = ["ParseDiagnostics", "max_dropped_lines"]


def _base_row(log_file: str, timestamp: str, source_index: int) -> ThreeDsMessageRow:
    return ThreeDsMessageRow(
        log_file=log_file,
        message_datetime=timestamp,
        message_type="",
        source_index=source_index,
    )


def _parse_json_array_payload(
    raw: str, diagnostics: ParseDiagnostics | None = None
) -> list[dict]:
    stripped = raw.strip()
    if not stripped.startswith("{") and not stripped.startswith("["):
        return []
    normalized = stripped if stripped.startswith("[") else f"[{stripped}]"
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError:
        if diagnostics is not None:
            diagnostics.record_drop(f"Malformed JSON array payload: {stripped[:120]}")
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _rows_from_json_array(
    log_file: str,
    timestamp: str,
    direction: str,
    raw_json: str,
    source_index: int,
    diagnostics: ParseDiagnostics | None = None,
) -> list[ThreeDsMessageRow]:
    rows: list[ThreeDsMessageRow] = []
    for payload in _parse_json_array_payload(raw_json, diagnostics):
        row = _base_row(log_file, timestamp, source_index)
        row.message_direction = direction
        apply_json_payload(row, payload)
        if row.message_type:
            rows.append(row)
    return rows


def _parse_line(
    log_file: str,
    line: str,
    source_index: int,
    diagnostics: ParseDiagnostics | None = None,
) -> list[ThreeDsMessageRow]:
    timestamp_match = TIMESTAMP_RE.match(line)
    if not timestamp_match:
        return []
    timestamp = timestamp_match.group(1)

    incoming_match = INCOMING_MESSAGE_PAYLOAD_RE.search(line)
    if incoming_match:
        return _rows_from_json_array(
            log_file, timestamp, "In", incoming_match.group(1), source_index, diagnostics
        )

    outgoing_match = OUTGOING_MESSAGE_PAYLOAD_RE.search(line)
    if outgoing_match:
        return _rows_from_json_array(
            log_file, timestamp, "Out", outgoing_match.group(1), source_index, diagnostics
        )

    rreq_status_match = RECEIVED_RREQ_STATUS_RE.search(line)
    if rreq_status_match:
        row = _base_row(log_file, timestamp, source_index)
        row.message_type = "RReqResult"
        row.three_ds_server_trans_id = rreq_status_match.group(1)
        row.rreq_result_status = rreq_status_match.group(2)
        row.rreq_result_reason = rreq_status_match.group(3)
        return [row]

    method_expired_match = METHOD_EXPIRED_RE.search(line)
    if method_expired_match:
        row = _base_row(log_file, timestamp, source_index)
        row.message_type = "MethodExpired"
        row.three_ds_server_trans_id = method_expired_match.group(1)
        return [row]

    return []


def parse_log_content(
    log_file: str,
    content: str,
    file_index: int = 0,
    diagnostics: ParseDiagnostics | None = None,
) -> list[ThreeDsMessageRow]:
    rows: list[ThreeDsMessageRow] = []
    for line_no, line in enumerate(content.splitlines()):
        source_index = file_index * 10_000_000 + line_no
        rows.extend(_parse_line(log_file, line, source_index, diagnostics))
    return rows


def parse_log_file(path: str | Path, log_file: str | None = None) -> list[ThreeDsMessageRow]:
    file_path = Path(path)
    display_name = log_file or file_path.name
    content = file_path.read_text(encoding="utf-8", errors="replace")
    return parse_log_content(display_name, content)


def parse_log_files(
    files: list[tuple[str, str]],
    sort_output: bool = True,
    diagnostics: ParseDiagnostics | None = None,
) -> list[ThreeDsMessageRow]:
    all_rows: list[ThreeDsMessageRow] = []
    for file_index, (log_file, content) in enumerate(files):
        all_rows.extend(parse_log_content(log_file, content, file_index, diagnostics))
    if sort_output:
        all_rows.sort(
            key=lambda row: (
                row.message_datetime,
                MESSAGE_SORT_ORDER.get(row.message_type, 999),
                row.source_index,
            )
        )
    return all_rows
