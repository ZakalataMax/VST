from __future__ import annotations

STATUS_PARSED = "parsed"
STATUS_READY = "ready"
STATUS_PARSING = "parsing"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"

STATUS_ICONS = {
    STATUS_PARSED: "✓",
    STATUS_READY: "○",
    STATUS_PARSING: "⟳",
    STATUS_PARTIAL: "⚠",
    STATUS_FAILED: "!",
}

STATUS_SORT = {
    STATUS_FAILED: 0,
    STATUS_PARTIAL: 1,
    STATUS_PARSING: 2,
    STATUS_READY: 3,
    STATUS_PARSED: 4,
}

STATUS_DISPLAY = {
    STATUS_PARSED: "Parsed",
    STATUS_READY: "Downloaded",
    STATUS_PARSING: "Parsing",
    STATUS_PARTIAL: "Partial",
    STATUS_FAILED: "Failed",
}


def format_row_count(row_count: int) -> str:
    if row_count >= 1_000_000:
        return f"{row_count / 1_000_000:.1f}M"
    if row_count >= 10_000:
        return f"{row_count / 1_000:.0f}k"
    return f"{row_count:,}"


def resolve_day_status(
    day: dict,
    *,
    parsing_dates: set[str] | None = None,
    failed_dates: dict[str, str] | None = None,
) -> str:
    date = day["date"]
    parsing_dates = parsing_dates or set()
    failed_dates = failed_dates or {}

    if date in failed_dates:
        return STATUS_FAILED
    if date in parsing_dates:
        return STATUS_PARSING
    csv_day = day.get("csv_day")
    if csv_day and csv_day.get("fullDay"):
        return STATUS_PARSED
    if csv_day:
        return STATUS_PARTIAL
    return STATUS_READY


def enrich_coverage_day(
    day: dict,
    *,
    parsing_dates: set[str] | None = None,
    failed_dates: dict[str, str] | None = None,
) -> dict:
    failed_dates = failed_dates or {}
    status = resolve_day_status(day, parsing_dates=parsing_dates, failed_dates=failed_dates)
    day["status"] = status
    day["status_icon"] = STATUS_ICONS[status]
    day["status_sort"] = STATUS_SORT[status]
    day["status_text"] = STATUS_DISPLAY[status]
    day["row_count_text"] = format_row_count(int(day.get("rowCount") or 0))
    csv_day = day.get("csv_day")
    day["parsed_row_count_text"] = format_row_count(int(csv_day["rowCount"])) if csv_day else "—"
    day["failed_message"] = failed_dates.get(day["date"], "")
    return day


def build_coverage_days(
    log_days: list[dict],
    csv_days: list[dict] | None = None,
    *,
    parsing_dates: set[str] | None = None,
    failed_dates: dict[str, str] | None = None,
) -> list[dict]:
    csv_by_date = {day["date"]: day for day in (csv_days or [])}
    log_by_date = {day["date"]: day for day in log_days}
    dates = sorted(set(log_by_date) | set(csv_by_date), reverse=True)

    result: list[dict] = []
    for date in dates:
        log_day = log_by_date.get(date, {})
        day = {
            "date": date,
            "partial": bool(log_day.get("partial")),
            "rowCount": log_day.get("rowCount", 0),
            "csv_day": csv_by_date.get(date),
        }
        enrich_coverage_day(day, parsing_dates=parsing_dates, failed_dates=failed_dates)
        result.append(day)
    return result
