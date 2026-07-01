from __future__ import annotations

import json
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
from app.services.email_sender import SmtpConfig, send_report_email
from app.services.file_report import export_report_xlsx
from app.services.log_storage import read_day_for_parse, save_elastic_log

DEFAULT_WINDOW_DAYS = 10

EmailSender = Callable[[SmtpConfig, str, str], None]


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


def _build_email_body(summary: DailyRunSummary) -> str:
    lines = [
        "VST daily report",
        f"Window: {summary.window[0]} .. {summary.window[-1]}",
        f"Downloaded days: {len(summary.downloaded)}",
        f"Parsed days: {len(summary.parsed)}",
        f"Report rows: {summary.report_rows}",
    ]
    if summary.dropped_counts:
        lines.append(f"Dropped rows/lines: {summary.dropped_counts}")
    if summary.failed:
        lines.append(f"Failures: {summary.failed}")
    return "\n".join(lines)


def run_daily_report(
    *,
    now: datetime | None = None,
    executor: Executor | None = None,
    email_sender: EmailSender | None = None,
    smtp_config: SmtpConfig | None = None,
    total_days: int = DEFAULT_WINDOW_DAYS,
) -> DailyRunSummary:
    now = now or datetime.now()
    today = now.date()
    today_iso = today.isoformat()
    window = rolling_window(today, total_days)
    summary = DailyRunSummary(started_at=now.isoformat(), window=window)
    threshold = max_dropped_lines()

    for day in window:
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
        for day in window
        if day != today_iso and day not in summary.parsed
    ]
    if missing_required:
        summary.failed["report"] = (
            "Missing parsed CSV for required day(s): " + ", ".join(missing_required)
        )
        summary.finished_at = datetime.now().isoformat()
        summary.ok = False
        return summary

    report_end = max(summary.parsed) if summary.parsed else window[-1]
    try:
        export = export_report_xlsx(
            mode="date",
            date_from=f"{window[0]} 00:00:00",
            date_to=f"{report_end} 23:59:59",
        )
        summary.report_path = export.output_path
        summary.report_rows = export.row_count
    except Exception as error:
        summary.failed["report"] = str(error)
        summary.finished_at = datetime.now().isoformat()
        summary.ok = False
        return summary

    config = smtp_config if smtp_config is not None else SmtpConfig.from_env()
    if config is None:
        summary.email_status = "skipped: SMTP not configured"
    else:
        sender = email_sender or (
            lambda cfg, body, path: send_report_email(
                cfg, body=body, attachment_path=path
            )
        )
        try:
            sender(config, _build_email_body(summary), summary.report_path)
            summary.email_status = f"sent to {', '.join(config.recipients)}"
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
    summary = run_daily_report()
    try:
        write_summary(summary)
    except OSError:
        pass
    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
    return 0 if summary.ok else 1


if __name__ == "__main__":
    sys.exit(main())
