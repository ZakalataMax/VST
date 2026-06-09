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

FILTER_ALL = "all"
FILTER_READY = "ready"
FILTER_ISSUES = "issues"
FILTER_PARSED = "parsed"

ISSUE_STATUSES = {STATUS_FAILED, STATUS_MISSING, STATUS_PARTIAL}
SELECTABLE_STATUSES = {STATUS_READY, STATUS_PARTIAL, STATUS_FAILED}


def acs_coverage_tooltip(log_day: dict | None) -> str:
    log_day = log_day or {}
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


def is_day_selectable(status: str) -> bool:
    return status in SELECTABLE_STATUSES


def filter_coverage_days(days: list[dict], filter_id: str) -> list[dict]:
    if filter_id == FILTER_ALL:
        return days
    if filter_id == FILTER_READY:
        return [day for day in days if day.get("status") == STATUS_READY]
    if filter_id == FILTER_ISSUES:
        return [day for day in days if day.get("status") in ISSUE_STATUSES]
    if filter_id == FILTER_PARSED:
        return [day for day in days if day.get("status") == STATUS_PARSED]
    return days


def ready_day_count(days: list[dict]) -> int:
    return sum(1 for day in days if day.get("status") == STATUS_READY)


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
    has_pair = bool(log_day and log_day.get("acs1") and log_day.get("acs2"))
    if not csv_day:
        return False, "Not parsed" if has_pair else "Incomplete"
    if has_pair and csv_day.get("fullDay"):
        return True, "Complete"
    return False, "Parsed"


def coverage_dots(log_day: dict | None) -> str:
    log_day = log_day or {}
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
    if not log_day.get("acs1") or not log_day.get("acs2"):
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


def sort_coverage_days(days: list[dict]) -> list[dict]:
    days.sort(key=lambda day: day["date"], reverse=True)
    days.sort(key=lambda day: day["status_sort"])
    return days


def count_status_stats(days: list[dict]) -> dict[str, int]:
    counts = {key: 0 for key in STATUS_SORT}
    for day in days:
        counts[day.get("status", STATUS_READY)] += 1
    return counts


def build_coverage_summary(days: list[dict]) -> str:
    with_pair = complete = total_rows = 0
    for day in days:
        log_day = day.get("log_day") or {}
        csv_day = day.get("csv_day")
        if log_day.get("acs1") and log_day.get("acs2"):
            with_pair += 1
        if day.get("complete"):
            complete += 1
        if csv_day:
            total_rows += int(csv_day.get("rowCount") or 0)
    return f"{len(days)}d · {with_pair} pairs · {complete} ok · {total_rows:,} rows"


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


def detect_acs_node(file_name: str) -> str | None:
    lowered = file_name.lower()
    if "acs1" in lowered:
        return "acs1"
    if "acs2" in lowered:
        return "acs2"
    return None


def sort_log_paths_for_upload(paths: list[str]) -> list[str]:
    def sort_key(path: str) -> tuple[str, int]:
        import re

        name = path.replace("\\", "/").split("/")[-1]
        dates = re.findall(r"(\d{4}-\d{2}-\d{2})", name)
        date = dates[0] if dates else ""
        node = 1 if detect_acs_node(name) == "acs2" else 0
        return date, node

    return sorted(paths, key=sort_key)


def parse_dates_from_file_ids(file_ids: list[str]) -> set[str]:
    dates: set[str] = set()
    for file_id in file_ids:
        if "/" in file_id:
            dates.add(file_id.split("/", 1)[0])
    return dates
