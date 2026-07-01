import csv
import io
import json
import os
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from app.jobs.daily_report import rolling_window, run_daily_report
from app.services import elastic_logs
from app.services.elastic_logs import ElasticRequestError
from app.services.email_sender import SmtpConfig, build_message

_RANGE_RE = re.compile(r">= '([^']+)' AND timestamp < '([^']+)'")

AREQ_PAYLOAD = (
    'Logger - Incoming message: [{"messageType":"AReq",'
    '"threeDSServerTransID":"t1","acctNumber":"4111111111111111"}].'
)


def _good_executor(body: str) -> str:
    data = json.loads(body)
    match = _RANGE_RE.search(data["query"])
    from_dt = datetime.fromisoformat(match.group(1))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["timestamp", "host", "app_name", "level", "message"])
    writer.writerow(
        [from_dt.isoformat(timespec="milliseconds"), "acss201", "solar-acs", "INFO", AREQ_PAYLOAD]
    )
    return buffer.getvalue()


def _executor_failing_on(target_day: str):
    def executor(body: str) -> str:
        data = json.loads(body)
        match = _RANGE_RE.search(data["query"])
        from_dt = datetime.fromisoformat(match.group(1))
        if from_dt.date().isoformat() == target_day:
            raise ElasticRequestError("HTTP 401", retryable=False)
        return _good_executor(body)

    return executor


class RollingWindowTest(unittest.TestCase):
    def test_window_has_total_days_ending_today(self) -> None:
        window = rolling_window(date(2026, 6, 25), total_days=10)
        self.assertEqual(len(window), 10)
        self.assertEqual(window[0], "2026-06-16")
        self.assertEqual(window[-1], "2026-06-25")


class DailyReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        keys = ("LOG_STORAGE_DIR", "CSV_STORAGE_DIR", "REPORT_OUTPUT_DIR")
        self._saved = {key: os.environ.get(key) for key in keys}
        base = Path(self._tmp.name)
        os.environ["LOG_STORAGE_DIR"] = str(base / "logs")
        os.environ["CSV_STORAGE_DIR"] = str(base / "csv")
        os.environ["REPORT_OUTPUT_DIR"] = str(base / "reports")

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def _now(self) -> datetime:
        return datetime(2026, 6, 25, 7, 0, 0, tzinfo=elastic_logs._tz())

    def test_successful_run_exports_and_emails(self) -> None:
        sent: list[tuple] = []
        config = SmtpConfig(
            host="smtp.local",
            port=587,
            tls="none",
            user="",
            password="",
            sender="vst@local",
            recipients=["ops@local"],
            subject="VST daily report",
        )
        summary = run_daily_report(
            now=self._now(),
            executor=_good_executor,
            email_sender=lambda cfg, body, path: sent.append((cfg, body, path)),
            smtp_config=config,
            total_days=2,
        )
        self.assertTrue(summary.ok, summary.failed)
        self.assertEqual(summary.parsed, ["2026-06-24", "2026-06-25"])
        self.assertTrue(Path(summary.report_path).exists())
        self.assertEqual(len(sent), 1)
        self.assertIn("ops@local", summary.email_status)

    def test_missing_required_day_fails_without_email(self) -> None:
        sent: list[tuple] = []
        summary = run_daily_report(
            now=self._now(),
            executor=_executor_failing_on("2026-06-24"),
            email_sender=lambda cfg, body, path: sent.append((cfg, body, path)),
            smtp_config=SmtpConfig(
                host="smtp.local",
                port=587,
                tls="none",
                user="",
                password="",
                sender="vst@local",
                recipients=["ops@local"],
                subject="s",
            ),
            total_days=2,
        )
        self.assertFalse(summary.ok)
        self.assertIn("2026-06-24", summary.failed.get("report", ""))
        self.assertEqual(sent, [])
        self.assertEqual(summary.report_path, "")

    def test_skips_email_when_not_configured(self) -> None:
        summary = run_daily_report(
            now=self._now(),
            executor=_good_executor,
            smtp_config=None,
            total_days=2,
        )
        self.assertTrue(summary.ok, summary.failed)
        self.assertIn("skipped", summary.email_status)


class EmailMessageTest(unittest.TestCase):
    def test_build_message_with_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            attachment = Path(tmp) / "report.xlsx"
            attachment.write_bytes(b"xlsx-bytes")
            config = SmtpConfig(
                host="smtp.local",
                port=587,
                tls="starttls",
                user="u",
                password="p",
                sender="from@local",
                recipients=["a@local", "b@local"],
                subject="Subject",
            )
            message = build_message(config, body="hello", attachment_path=attachment)
            self.assertEqual(message["From"], "from@local")
            self.assertEqual(message["To"], "a@local, b@local")
            self.assertEqual(message["Subject"], "Subject")
            attachments = list(message.iter_attachments())
            self.assertEqual(len(attachments), 1)
            self.assertEqual(attachments[0].get_filename(), "report.xlsx")


if __name__ == "__main__":
    unittest.main()
