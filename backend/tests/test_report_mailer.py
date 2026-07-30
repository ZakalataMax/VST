import os
import unittest
from unittest.mock import patch

from app.services import report_mailer
from app.services.outlook_sender import outlook_available


class ReportMailerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            key: os.environ.get(key) for key in ("REPORT_EMAIL_TO",)
        }
        for key in self._saved:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_outlook_unavailable_reports_status(self) -> None:
        with patch.object(report_mailer, "outlook_available", return_value=False):
            status = report_mailer.send_report(
                recipients=["a@local"], subject="s", body="b", attachment_path="x.xlsx"
            )
        self.assertIn("Outlook automation unavailable", status)

    def test_outlook_success_reports_recipients(self) -> None:
        with patch.object(report_mailer, "outlook_available", return_value=True), patch.object(
            report_mailer, "send_via_outlook"
        ) as mock_send:
            status = report_mailer.send_report(
                recipients=["a@local", "b@local"], subject="s", body="b", attachment_path="x.xlsx"
            )
        mock_send.assert_called_once()
        self.assertIn("a@local", status)
        self.assertIn("Outlook", status)

    def test_outlook_available_returns_bool(self) -> None:
        self.assertIsInstance(outlook_available(), bool)

    def test_recipients_from_env_falls_back_to_default_when_unset(self) -> None:
        self.assertEqual(report_mailer.recipients_from_env(), [report_mailer.DEFAULT_RECIPIENT])

    def test_recipients_from_env_empty_disables_default(self) -> None:
        os.environ["REPORT_EMAIL_TO"] = ""
        self.assertEqual(report_mailer.recipients_from_env(), [])

    def test_recipients_from_env_reads_configured_value(self) -> None:
        os.environ["REPORT_EMAIL_TO"] = "a@local, b@local"
        self.assertEqual(report_mailer.recipients_from_env(), ["a@local", "b@local"])


if __name__ == "__main__":
    unittest.main()
