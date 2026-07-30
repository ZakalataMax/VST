from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from app.config import load_env_file
from app.parsers.acs_log_parser import (
    ParseDiagnostics,
    max_dropped_lines,
    parse_log_files,
)
from app.paths import get_report_output_dir
from app.services.csv_storage import delete_csv_day, save_daily_csvs
from app.services.elastic_logs import Executor, download_day
from app.services.file_report import export_report_xlsx
from app.services.log_storage import read_day_for_parse, save_elastic_log
from app.services.report_mailer import (
    build_daily_report_body,
    recipients_from_env,
    send_report,
    subject_from_env,
)

DEFAULT_WINDOW_DAYS = 10
DEFAULT_DOWNLOAD_DAYS = 2
DEFAULT_REPORT_DAYS = 10

MailSender = Callable[..., str]


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass
class DailyRunSummary:
    started_at: str
    window: list[str] = field(default_factory=list)
    downloaded: list[str] = field(default_factory=list)
    parsed: list[str] = field(default_factory=list)
    dropped_counts: dict[str, int] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    report_path: str = ""
    report_rows: int = 0
    pivot_status: str = ""
    email_status: str = ""
    ok: bool = False
    finished_at: str = ""


def rolling_window(today: date, total_days: int = DEFAULT_WINDOW_DAYS) -> list[str]:
    start = today - timedelta(days=total_days - 1)
    return [(start + timedelta(days=offset)).isoformat() for offset in range(total_days)]


def _process_day(
    day: str,
    *,
    now: datetime,
    executor: Executor | None,
    summary: DailyRunSummary,
    threshold: int,
) -> None:
    result = download_day(day, now=now, executor=executor)
    save_elastic_log(
        day,
        result.content,
        partial=result.partial,
        row_count=result.row_count,
        min_datetime=result.min_datetime,
        max_datetime=result.max_datetime,
    )
    summary.downloaded.append(day)
    if result.dropped_count:
        summary.dropped_counts[day] = result.dropped_count

    delete_csv_day(day)
    stored = read_day_for_parse(day)
    diagnostics = ParseDiagnostics()
    rows = parse_log_files(stored, diagnostics=diagnostics)
    if diagnostics.dropped_count > threshold:
        summary.failed[day] = (
            f"{diagnostics.dropped_count} malformed line(s) exceeded threshold "
            f"({threshold})."
        )
        return
    save_daily_csvs(rows)
    summary.parsed.append(day)
    if diagnostics.dropped_count:
        summary.dropped_counts[day] = (
            summary.dropped_counts.get(day, 0) + diagnostics.dropped_count
        )


def run_daily_report(
    *,
    now: datetime | None = None,
    executor: Executor | None = None,
    mail_sender: MailSender | None = None,
    download_days: int = DEFAULT_DOWNLOAD_DAYS,
    report_days: int = DEFAULT_REPORT_DAYS,
) -> DailyRunSummary:
    now = now or datetime.now()
    today = now.date()
    today_iso = today.isoformat()
    download_window = rolling_window(today, download_days)
    report_window = rolling_window(today, report_days)
    summary = DailyRunSummary(started_at=now.isoformat(), window=report_window)
    threshold = max_dropped_lines()

    for day in download_window:
        try:
            _process_day(
                day,
                now=now,
                executor=executor,
                summary=summary,
                threshold=threshold,
            )
        except Exception as error:
            summary.failed[day] = str(error)

    missing_required = [
        day
        for day in download_window
        if day != today_iso and day not in summary.parsed
    ]
    if missing_required:
        summary.failed["report"] = (
            "Missing parsed CSV for required day(s): " + ", ".join(missing_required)
        )
        summary.finished_at = datetime.now().isoformat()
        summary.ok = False
        return summary

    report_end = report_window[-1]
    if today_iso not in summary.parsed:
        earlier_days = [day for day in report_window if day != today_iso]
        report_end = earlier_days[-1] if earlier_days else report_window[0]

    try:
        export = export_report_xlsx(
            mode="date",
            date_from=f"{report_window[0]} 00:00:00",
            date_to=f"{report_end} 23:59:59",
            native_pivot=True,
        )
        summary.report_path = str(export.output_path)
        summary.report_rows = export.row_count
        summary.pivot_status = (
            export.pivot_error if export.pivot_error
            else ("pivot added" if export.pivot_added else "no pivot")
        )
    except Exception as error:
        summary.failed["report"] = str(error)
        summary.finished_at = datetime.now().isoformat()
        summary.ok = False
        return summary

    recipients = recipients_from_env()
    if not recipients:
        summary.email_status = "skipped: REPORT_EMAIL_TO not configured"
    else:
        sender = mail_sender or send_report
        try:
            summary.email_status = sender(
                recipients=recipients,
                subject=subject_from_env(),
                body=build_daily_report_body(
                    window=summary.window,
                    report_rows=summary.report_rows,
                    pivot_status=summary.pivot_status,
                    dropped_counts=summary.dropped_counts,
                    failed=summary.failed,
                ),
                attachment_path=summary.report_path,
            )
        except Exception as error:
            summary.email_status = f"failed: {error}"
            summary.failed["email"] = str(error)

    summary.finished_at = datetime.now().isoformat()
    summary.ok = not summary.failed
    return summary


def write_summary(summary: DailyRunSummary, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or get_report_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"run-summary-{stamp}.json"
    json_path.write_text(
        json.dumps(asdict(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return json_path


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    download_days = _int_env("DAILY_JOB_DOWNLOAD_DAYS", DEFAULT_DOWNLOAD_DAYS)
    report_days = _int_env("DAILY_JOB_REPORT_DAYS", DEFAULT_REPORT_DAYS)
    summary = run_daily_report(download_days=download_days, report_days=report_days)
    try:
        write_summary(summary)
    except OSError:
        pass
    if sys.stdout is not None:
        print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
