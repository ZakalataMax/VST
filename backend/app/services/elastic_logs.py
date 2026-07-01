from __future__ import annotations

import base64
import csv
import io
import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from typing import Callable

DEFAULT_URL = (
    "https://logs.proc.lan/s/solar-prod/api/console/proxy?path=_sql?format=csv&method=POST"
)
DEFAULT_USER = "solar"
DEFAULT_INDEX = "prod-*"
DEFAULT_HOSTS = ("acss201", "acss202")
DEFAULT_APP_NAME = "solar-acs"
DEFAULT_TZ_OFFSET = "+03:00"
DEFAULT_TIME_ZONE = "Europe/Athens"

INITIAL_CHUNK_MINUTES = 30
MIN_CHUNK_MINUTES = 1
FETCH_SIZE = 10000
QUERY_LIMIT = 100000
REQUEST_TIMEOUT = 180
DEFAULT_MAX_DROPPED_ROWS = 100

CSV_FIELDS = ("timestamp", "host", "app_name", "level", "message")

ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]
Executor = Callable[[str], str]


class ElasticError(Exception):
    pass


class ElasticConfigError(ElasticError):
    pass


class ElasticRequestError(ElasticError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ElasticDownloadCancelled(ElasticError):
    pass


@dataclass
class ElasticCredentials:
    user: str
    password: str


@dataclass
class ElasticDownloadResult:
    log_date: str
    content: str
    row_count: int
    partial: bool
    min_datetime: str
    max_datetime: str
    dropped_count: int = 0


def get_credentials() -> ElasticCredentials:
    password = os.getenv("ELASTIC_PASS", "")
    if not password:
        raise ElasticConfigError(
            "ELASTIC_PASS is not set. Set the ELASTIC_PASS environment variable "
            "with your Elastic password before downloading logs."
        )
    user = os.getenv("ELASTIC_USER", "") or DEFAULT_USER
    return ElasticCredentials(user=user, password=password)


def _tz() -> timezone:
    offset = os.getenv("ELASTIC_TZ_OFFSET", "") or DEFAULT_TZ_OFFSET
    sign = 1
    text = offset.strip()
    if text.startswith("-"):
        sign = -1
        text = text[1:]
    elif text.startswith("+"):
        text = text[1:]
    hours_str, _, minutes_str = text.partition(":")
    hours = int(hours_str or 0)
    minutes = int(minutes_str or 0)
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def _hosts() -> tuple[str, ...]:
    raw = os.getenv("ELASTIC_HOSTS", "")
    if not raw:
        return DEFAULT_HOSTS
    hosts = tuple(part.strip() for part in raw.split(",") if part.strip())
    return hosts or DEFAULT_HOSTS


def build_query_body(from_dt: datetime, to_dt: datetime) -> str:
    hosts = ", ".join(f"'{host}'" for host in _hosts())
    app_name = os.getenv("ELASTIC_APP_NAME", "") or DEFAULT_APP_NAME
    index = os.getenv("ELASTIC_INDEX", "") or DEFAULT_INDEX
    time_zone = os.getenv("ELASTIC_TIME_ZONE", "") or DEFAULT_TIME_ZONE
    from_text = from_dt.isoformat(timespec="milliseconds")
    to_text = to_dt.isoformat(timespec="milliseconds")
    query = (
        "SELECT timestamp, host, app_name, level, message "
        f'FROM "{index}" '
        f"WHERE timestamp >= '{from_text}' AND timestamp < '{to_text}' "
        f"AND app_name = '{app_name}' AND host IN ({hosts}) "
        f"ORDER BY timestamp ASC LIMIT {QUERY_LIMIT}"
    )
    return json.dumps(
        {
            "query": query,
            "fetch_size": FETCH_SIZE,
            "time_zone": time_zone,
        }
    )


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def verify_tls_enabled() -> bool:
    if os.getenv("ELASTIC_CA_BUNDLE", "").strip():
        return True
    return _is_truthy(os.getenv("ELASTIC_VERIFY_TLS", ""))


def build_ssl_context() -> ssl.SSLContext:
    ca_bundle = os.getenv("ELASTIC_CA_BUNDLE", "").strip()
    if not verify_tls_enabled():
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    return ssl.create_default_context(cafile=ca_bundle or None)


def _default_executor(body: str) -> str:
    credentials = get_credentials()
    url = os.getenv("ELASTIC_URL", "") or DEFAULT_URL
    token = base64.b64encode(
        f"{credentials.user}:{credentials.password}".encode("utf-8")
    ).decode("ascii")
    request = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-elastic-internal-origin": "kibana",
            "kbn-xsrf": "anything",
            "Authorization": f"Basic {token}",
        },
    )
    context = build_ssl_context()
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT, context=context) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        retryable = error.code >= 500
        raise ElasticRequestError(
            f"Elastic request failed with HTTP {error.code}", retryable=retryable
        ) from error
    except urllib.error.URLError as error:
        raise ElasticRequestError(f"Elastic request failed: {error.reason}") from error
    except TimeoutError as error:
        raise ElasticRequestError("Elastic request timed out", retryable=True) from error


def _normalize_timestamp(raw: str) -> str:
    parsed = datetime.fromisoformat(raw)
    millis = parsed.microsecond // 1000
    return parsed.strftime("%Y-%m-%d %H:%M:%S.") + f"{millis:03d}"


def _max_dropped_rows() -> int:
    raw = os.getenv("ELASTIC_MAX_DROPPED", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_DROPPED_ROWS
    return value if value >= 0 else DEFAULT_MAX_DROPPED_ROWS


def _parse_csv_rows(text: str) -> tuple[list[tuple[str, str]], int]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[tuple[str, str]] = []
    dropped = 0
    for record in reader:
        raw_timestamp = (record.get("timestamp") or "").strip()
        if not raw_timestamp:
            dropped += 1
            continue
        host = (record.get("host") or "").strip()
        level = (record.get("level") or "").strip() or "INFO"
        message = (record.get("message") or "").replace("\r", " ").replace("\n", " ")
        try:
            normalized = _normalize_timestamp(raw_timestamp)
        except ValueError:
            dropped += 1
            continue
        line = f"{normalized} {level} [{host}] {message}"
        rows.append((raw_timestamp, line))
    return rows, dropped


def _looks_like_csv(text: str) -> bool:
    head = text.lstrip()[:200].lower()
    if head.startswith("<"):
        return False
    return "timestamp" in head.split("\n", 1)[0]


def _fetch_range(
    from_dt: datetime,
    to_dt: datetime,
    executor: Executor,
) -> str:
    body = build_query_body(from_dt, to_dt)
    text = executor(body)
    if not _looks_like_csv(text):
        raise ElasticRequestError(
            "Elastic returned an unexpected (non-CSV) response", retryable=True
        )
    return text


def _check_cancel(should_cancel: CancelCallback | None) -> None:
    if should_cancel is not None and should_cancel():
        raise ElasticDownloadCancelled()


def _collect_range(
    from_dt: datetime,
    to_dt: datetime,
    executor: Executor,
    rows: list[tuple[str, str]],
    progress: ProgressCallback | None,
    progress_state: dict,
    should_cancel: CancelCallback | None = None,
) -> None:
    _check_cancel(should_cancel)
    minutes = max(int((to_dt - from_dt).total_seconds() // 60), 0)
    try:
        text = _fetch_range(from_dt, to_dt, executor)
    except ElasticRequestError as error:
        if not error.retryable or minutes <= MIN_CHUNK_MINUTES:
            raise
        middle = from_dt + timedelta(minutes=(minutes + 1) // 2)
        if middle <= from_dt or middle >= to_dt:
            raise
        _collect_range(
            from_dt, middle, executor, rows, progress, progress_state, should_cancel
        )
        _collect_range(
            middle, to_dt, executor, rows, progress, progress_state, should_cancel
        )
        return

    chunk_rows, dropped = _parse_csv_rows(text)
    returned_records = len(chunk_rows) + dropped
    if returned_records >= QUERY_LIMIT:
        if minutes <= MIN_CHUNK_MINUTES:
            raise ElasticError(
                f"Elastic returned the row limit ({QUERY_LIMIT}) for the smallest "
                f"{minutes}-minute window "
                f"{from_dt.strftime('%Y-%m-%d %H:%M')}-{to_dt.strftime('%H:%M')}. "
                "Logs would be truncated and cannot be split further."
            )
        middle = from_dt + timedelta(minutes=(minutes + 1) // 2)
        if middle <= from_dt or middle >= to_dt:
            raise ElasticError(
                f"Elastic returned the row limit ({QUERY_LIMIT}) for "
                f"{from_dt.strftime('%Y-%m-%d %H:%M')}-{to_dt.strftime('%H:%M')} "
                "and the window cannot be split further. Logs would be truncated."
            )
        _collect_range(
            from_dt, middle, executor, rows, progress, progress_state, should_cancel
        )
        _collect_range(
            middle, to_dt, executor, rows, progress, progress_state, should_cancel
        )
        return

    rows.extend(chunk_rows)
    progress_state["dropped"] += dropped
    progress_state["done"] += minutes
    if progress is not None:
        label = (
            f"Downloading {from_dt.strftime('%H:%M')}-{to_dt.strftime('%H:%M')}"
        )
        progress(progress_state["done"], progress_state["total"], label)
    _check_cancel(should_cancel)


def should_skip_download(log_date: str, *, download_complete: bool, today: str) -> bool:
    if not download_complete:
        return False
    if log_date >= today:
        return False
    return True


def iter_days(date_from: str, date_to: str) -> list[str]:
    start = date_cls.fromisoformat(date_from)
    end = date_cls.fromisoformat(date_to)
    if end < start:
        start, end = end, start
    days: list[str] = []
    cursor = start
    while cursor <= end:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def plan_download_dates(
    date_from: str,
    date_to: str,
    *,
    today: str,
    downloaded: set[str],
) -> tuple[list[str], list[str], list[str]]:
    to_download: list[str] = []
    skipped: list[str] = []
    future: list[str] = []
    for day in iter_days(date_from, date_to):
        if day > today:
            future.append(day)
            continue
        if should_skip_download(day, download_complete=day in downloaded, today=today):
            skipped.append(day)
            continue
        to_download.append(day)
    return to_download, skipped, future


def resolve_day_bounds(
    log_date: str,
    now: datetime | None = None,
) -> tuple[datetime, datetime, bool]:
    tz = _tz()
    day = date_cls.fromisoformat(log_date)
    start = datetime.combine(day, time.min, tzinfo=tz)
    full_end = start + timedelta(days=1)
    current = now.astimezone(tz) if now is not None else datetime.now(tz)
    if current >= full_end:
        return start, full_end, False
    if current <= start:
        raise ElasticError(f"Selected day {log_date} is in the future.")
    return start, current, True


def download_day(
    log_date: str,
    *,
    now: datetime | None = None,
    executor: Executor | None = None,
    progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> ElasticDownloadResult:
    runner = executor or _default_executor
    start, end, partial = resolve_day_bounds(log_date, now)

    total_minutes = max(int((end - start).total_seconds() // 60), 1)
    progress_state = {"done": 0, "total": total_minutes, "dropped": 0}
    rows: list[tuple[str, str]] = []

    cursor = start
    while cursor < end:
        _check_cancel(should_cancel)
        chunk_end = min(cursor + timedelta(minutes=INITIAL_CHUNK_MINUTES), end)
        _collect_range(
            cursor,
            chunk_end,
            runner,
            rows,
            progress,
            progress_state,
            should_cancel,
        )
        cursor = chunk_end

    dropped_count = progress_state["dropped"]
    threshold = _max_dropped_rows()
    if dropped_count > threshold:
        raise ElasticError(
            f"Day {log_date}: {dropped_count} Elastic rows had missing or invalid "
            f"timestamps, exceeding the allowed threshold ({threshold}). "
            "Aborting to avoid silent data loss."
        )

    rows.sort(key=lambda item: item[0])
    lines = [line for _, line in rows]
    content = "\n".join(lines)
    if content:
        content += "\n"

    min_datetime = ""
    max_datetime = ""
    if rows:
        min_datetime = _normalize_timestamp(rows[0][0])
        max_datetime = _normalize_timestamp(rows[-1][0])

    return ElasticDownloadResult(
        log_date=log_date,
        content=content,
        row_count=len(rows),
        partial=partial,
        min_datetime=min_datetime,
        max_datetime=max_datetime,
        dropped_count=dropped_count,
    )
