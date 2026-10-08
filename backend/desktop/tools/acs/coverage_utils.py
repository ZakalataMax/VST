from __future__ import annotations

STATUS_PARSED = "parsed"
STATUS_READY = "ready"
STATUS_PARSING = "parsing"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing"
STATUS_FAILED = "failed"

STATUS_ICONS = {
    STATUS_PARSED: "✓",
    STATUS_READY: "○",
    STATUS_PARSING: "⟳",
    STATUS_PARTIAL: "⚠",
    STATUS_MISSING: "✕",
    STATUS_FAILED: "!",
}

STATUS_SORT = {
    STATUS_FAILED: 0,
    STATUS_MISSING: 1,
    STATUS_PARTIAL: 2,
    STATUS_PARSING: 3,
    STATUS_READY: 4,
    STATUS_PARSED: 5,
}

PARSE_LABELS = {
    STATUS_PARSED: "done",
    STATUS_READY: "ready",
    STATUS_PARSING: "run",
    STATUS_PARTIAL: "part",
    STATUS_MISSING: "miss",
    STATUS_FAILED: "fail",
}

STATUS_DISPLAY = {
    STATUS_PARSED: "Parsed",
    STATUS_READY: "Ready",
    STATUS_PARSING: "Parsing",
    STATUS_PARTIAL: "Partial",
    STATUS_MISSING: "Missing",
    STATUS_FAILED: "Failed",
}

ACTION_PARSE = "parse"
ACTION_REPARSE = "reparse"
ACTION_REPORT = "report"
ACTION_NONE = "none"

ACTION_LABELS = {
    ACTION_PARSE: "Parse",
    ACTION_REPARSE: "Re-parse",
    ACTION_REPORT: "Report",
    ACTION_NONE: "—",
}

def day_has_logs(log_day: dict | None) -> bool:
    log_day = log_day or {}
    if log_day.get("elastic"):
        return True
    return bool(log_day.get("acs1") and log_day.get("acs2"))


def acs_coverage_tooltip(log_day: dict | None) -> str:
    log_day = log_day or {}
    if log_day.get("elastic"):
        return "Source: Elastic (solar-acs)"
    acs1 = "yes" if log_day.get("acs1") else "no"
    acs2 = "yes" if log_day.get("acs2") else "no"
    return f"ACS1: {acs1} · ACS2: {acs2}"


def action_for_status(status: str) -> str:
    if status == STATUS_READY:
        return ACTION_PARSE
    if status in (STATUS_PARTIAL, STATUS_FAILED):
        return ACTION_REPARSE
    if status == STATUS_PARSED:
        return ACTION_REPORT
    return ACTION_NONE


def action_label_for_status(status: str) -> str:
    return ACTION_LABELS[action_for_status(status)]


def day_files_tooltip(day: dict) -> str:
    files = day.get("files") or []
    if files:
        return " · ".join(file.get("filename", "") for file in files[:2])
    return acs_coverage_tooltip(day.get("log_day"))


def build_day_tooltip(day: dict) -> str:
    parts = [
        day.get("date", ""),
        day.get("status_text", ""),
        day_files_tooltip(day),
    ]
    if day.get("failed_message"):
        parts.append(day["failed_message"])
    row_count = day.get("row_count_text", "")
    if row_count and row_count != "—":
        parts.append(f"{row_count} rows")
    return " · ".join(part for part in parts if part)


def get_day_coverage_status(log_day: dict | None, csv_day: dict | None) -> tuple[bool, str]:
    has_logs = day_has_logs(log_day)
    if not csv_day:
        return False, "Not parsed" if has_logs else "Incomplete"
    if has_logs and csv_day.get("fullDay"):
        return True, "Complete"
    return False, "Parsed"


def coverage_dots(log_day: dict | None) -> str:
    log_day = log_day or {}
    if log_day.get("elastic"):
        return "EL"
    first = "●" if log_day.get("acs1") else "○"
    second = "●" if log_day.get("acs2") else "○"
    return f"{first}{second}"


def format_row_count(csv_day: dict | None) -> str:
    if not csv_day:
        return "—"
    count = int(csv_day.get("rowCount") or 0)
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 10_000:
        return f"{count / 1_000:.0f}k"
    return f"{count:,}"


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

    log_day = day.get("log_day") or {}
    if not day_has_logs(log_day):
        return STATUS_MISSING
    if day.get("complete"):
        return STATUS_PARSED
    if day.get("csv_day"):
        return STATUS_PARTIAL
    return STATUS_READY


def enrich_coverage_day(
    day: dict,
    *,
    parsing_dates: set[str] | None = None,
    failed_dates: dict[str, str] | None = None,
) -> dict:
    parsing_dates = parsing_dates or set()
    failed_dates = failed_dates or {}
    status = resolve_day_status(day, parsing_dates=parsing_dates, failed_dates=failed_dates)
    day["status"] = status
    day["status_icon"] = STATUS_ICONS[status]
    day["status_sort"] = STATUS_SORT[status]
    day["coverage_dots"] = coverage_dots(day.get("log_day"))
    day["row_count_text"] = format_row_count(day.get("csv_day"))
    day["parse_label"] = PARSE_LABELS[status]
    day["status_text"] = STATUS_DISPLAY[status]
    day["acs_tooltip"] = acs_coverage_tooltip(day.get("log_day"))
    day["action"] = action_for_status(status)
    day["action_label"] = action_label_for_status(status)
    day["failed_message"] = failed_dates.get(day["date"], "")
    return day


def build_coverage_days(
    files: list[dict],
    log_days: list[dict],
    csv_days: list[dict],
    *,
    parsing_dates: set[str] | None = None,
    failed_dates: dict[str, str] | None = None,
) -> list[dict]:
    log_day_by_date = {day["date"]: day for day in log_days}
    csv_day_by_date = {day["date"]: day for day in csv_days}
    files_by_date: dict[str, list[dict]] = {}

    for file in files:
        log_date = file.get("logDate") or file.get("log_date")
        if not log_date:
            continue
        files_by_date.setdefault(log_date, []).append(file)

    dates = sorted(
        set(files_by_date) | {day["date"] for day in log_days} | {day["date"] for day in csv_days},
        reverse=True,
    )

    result: list[dict] = []
    for date in dates:
        day_files = files_by_date.get(date, [])
        log_day = log_day_by_date.get(date) or {
            "acs1": any(f.get("acsNode") == "acs1" for f in day_files),
            "acs2": any(f.get("acsNode") == "acs2" for f in day_files),
            "elastic": any(f.get("acsNode") == "elastic" for f in day_files),
        }
        csv_day = csv_day_by_date.get(date)
        complete, label = get_day_coverage_status(log_day, csv_day)
        day = {
            "date": date,
            "files": day_files,
            "log_day": log_day,
            "csv_day": csv_day,
            "complete": complete,
            "status_label": label,
        }
        enrich_coverage_day(
            day,
            parsing_dates=parsing_dates,
            failed_dates=failed_dates,
        )
        result.append(day)

    return result
