from __future__ import annotations


def get_day_coverage_status(log_day: dict | None, csv_day: dict | None) -> tuple[bool, str]:
    has_pair = bool(log_day and log_day.get("acs1") and log_day.get("acs2"))
    if not csv_day:
        return False, "Not parsed" if has_pair else "Incomplete"
    if has_pair and csv_day.get("fullDay"):
        return True, "Complete"
    return False, "Parsed"


def build_coverage_days(
    files: list[dict],
    log_days: list[dict],
    csv_days: list[dict],
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
        result.append(
            {
                "date": date,
                "files": day_files,
                "log_day": log_day,
                "csv_day": csv_day,
                "complete": complete,
                "status_label": label,
            }
        )
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
