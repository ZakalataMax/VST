from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import duckdb

from app.common.elastic_logs import DEFAULT_TIME_ZONE

ST_LOUIS_TIME_ZONE = ZoneInfo("America/Chicago")
_MESSAGE_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S")


def _source_log_time_zone() -> ZoneInfo:
    name = os.getenv("ELASTIC_TIME_ZONE", "").strip() or DEFAULT_TIME_ZONE
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_TIME_ZONE)


def _to_st_louis_date(message_datetime: str | None) -> str:
    text = (message_datetime or "").strip()
    if not text:
        return ""
    parsed = None
    for fmt in _MESSAGE_DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return ""
    localized = parsed.replace(tzinfo=_source_log_time_zone())
    converted = localized.astimezone(ST_LOUIS_TIME_ZONE)
    return converted.strftime("%Y-%m-%d")


def register_time_zone_functions(connection: duckdb.DuckDBPyConnection) -> None:
    connection.create_function("vst_st_louis_date", _to_st_louis_date)
