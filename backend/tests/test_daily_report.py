import csv
import io
import json
import os
import re
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from app.jobs.daily_report import rolling_window, run_daily_report
from app.parsers.models import MessageRow
from app.services import elastic_logs
from app.services.csv_storage import save_daily_csvs
from app.services.elastic_logs import ElasticRequestError

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
        keys = ("LOG_STORAGE_DIR", "CSV_STORAGE_DIR", "REPORT_OUTPUT_DIR", "REPORT_EMAIL_TO")
        self._saved = {key: os.environ.get(key) for key in keys}
        os.environ.pop("REPORT_EMAIL_TO", None)
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
        os.environ["REPORT_EMAIL_TO"] = "ops@local"
        sent: list[dict] = []

        def fake_sender(**kwargs) -> str:
            sent.append(kwargs)
            return f"sent to {', '.join(kwargs['recipients'])}"

        summary = run_daily_report(
            now=self._now(),
            executor=_good_executor,
            mail_sender=fake_sender,
            download_days=2,
            report_days=2,
        )
        self.assertTrue(summary.ok, summary.failed)
        self.assertEqual(summary.parsed, ["2026-06-24", "2026-06-25"])
        self.assertTrue(Path(summary.report_path).exists())
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["recipients"], ["ops@local"])
        self.assertIn("ops@local", summary.email_status)
        self.assertTrue(summary.pivot_status)

    def test_missing_required_day_fails_without_email(self) -> None:
        os.environ["REPORT_EMAIL_TO"] = "ops@local"
        sent: list[dict] = []

        def fake_sender(**kwargs) -> str:
            sent.append(kwargs)
            return "sent"

        summary = run_daily_report(
            now=self._now(),
            executor=_executor_failing_on("2026-06-24"),
            mail_sender=fake_sender,
            download_days=2,
            report_days=2,
        )
        self.assertFalse(summary.ok)
        self.assertIn("2026-06-24", summary.failed.get("report", ""))
        self.assertEqual(sent, [])
        self.assertEqual(summary.report_path, "")

    def test_skips_email_when_not_configured(self) -> None:
        os.environ["REPORT_EMAIL_TO"] = ""
        summary = run_daily_report(
            now=self._now(),
            executor=_good_executor,
            download_days=2,
            report_days=2,
        )
        self.assertTrue(summary.ok, summary.failed)
        self.assertIn("skipped", summary.email_status)

    def test_download_window_smaller_than_report_window(self) -> None:
        # Report window is 2026-06-16..2026-06-25; the download window only refreshes the
        # last 2 days, so every earlier day needs a pre-existing parsed CSV on disk.
        for day_offset in range(8):
            day = date(2026, 6, 16) + timedelta(days=day_offset)
            save_daily_csvs(
                [
                    MessageRow(
                        log_file="elastic.log",
                        message_datetime=f"{day.isoformat()} 10:00:00.000",
                        message_type="AReq",
                        three_ds_server_trans_id=f"old-txn-{day_offset}",
                        acct_number="4111111111111111",
                    )
                ]
            )

        summary = run_daily_report(
            now=self._now(),
            executor=_good_executor,
            download_days=2,
            report_days=10,
        )

        self.assertTrue(summary.ok, summary.failed)
        self.assertEqual(summary.downloaded, ["2026-06-24", "2026-06-25"])
        self.assertEqual(summary.parsed, ["2026-06-24", "2026-06-25"])
        self.assertEqual(summary.window[0], "2026-06-16")
        self.assertEqual(summary.window[-1], "2026-06-25")
        self.assertTrue(Path(summary.report_path).exists())


if __name__ == "__main__":
    unittest.main()
