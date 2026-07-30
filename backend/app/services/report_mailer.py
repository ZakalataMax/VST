from __future__ import annotations

import os
from pathlib import Path

from app.services.outlook_sender import outlook_available, send_via_outlook

# Everything that controls where/what the report email says lives here - edit these to
# change the recipient(s), subject, or body text without hunting through the rest of the
# codebase. Recipient(s) and subject can be overridden via REPORT_EMAIL_TO /
# REPORT_EMAIL_SUBJECT in .env; DEFAULT_RECIPIENT / DEFAULT_SUBJECT are the built-in
# fallbacks used when those env vars aren't set at all (set REPORT_EMAIL_TO= to an empty
# value in .env to disable emailing instead of falling back to DEFAULT_RECIPIENT).
DEFAULT_RECIPIENT = "m.zakalata@ornament-soft.com"
DEFAULT_SUBJECT = "ACS Approval Rate daily report"


def recipients_from_env() -> list[str]:
    raw = os.getenv("REPORT_EMAIL_TO")
    if raw is None:
        return [DEFAULT_RECIPIENT]
    return [part.strip() for part in raw.split(",") if part.strip()]


def subject_from_env() -> str:
    return os.getenv("REPORT_EMAIL_SUBJECT", DEFAULT_SUBJECT).strip() or DEFAULT_SUBJECT


def build_daily_report_body(
    *,
    window: list[str],
    report_rows: int,
    pivot_status: str,
    dropped_counts: dict[str, int],
    failed: dict[str, str],
) -> str:
    lines = [
        DEFAULT_SUBJECT,
        f"От : {window[0]}  До  {window[-1]}",
        f"Report rows: {report_rows}",
    ]
    if pivot_status:
        lines.append(f"Pivot: {pivot_status}")
    if dropped_counts:
        lines.append(f"Dropped rows/lines: {dropped_counts}")
    if failed:
        lines.append(f"Failures: {failed}")
    return "\n".join(lines)


def send_report(
    *,
    recipients: list[str],
    subject: str,
    body: str,
    attachment_path: str | Path,
) -> str:
    if not outlook_available():
        return "Outlook automation unavailable (pywin32 not installed)"
    try:
        send_via_outlook(
            recipients=recipients, subject=subject, body=body, attachment_path=attachment_path
        )
    except Exception as error:
        return f"failed: {error}"
    return f"sent via Outlook to {', '.join(recipients)}"
