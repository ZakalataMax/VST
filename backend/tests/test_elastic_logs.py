import http.server
import json
import os
import re
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.services import elastic_logs
from app.services.elastic_logs import (
    ElasticConfigError,
    ElasticRequestError,
    download_day,
    get_credentials,
    iter_days,
    plan_download_dates,
    resolve_day_bounds,
    should_skip_download,
)

_RANGE_RE = re.compile(r">= '([^']+)' AND timestamp < '([^']+)'")


def _make_executor(fail_above_minutes=None, calls=None, rows_per_chunk=1):
    def executor(body: str) -> str:
        data = json.loads(body)
        match = _RANGE_RE.search(data["query"])
        from_dt = datetime.fromisoformat(match.group(1))
        to_dt = datetime.fromisoformat(match.group(2))
        minutes = (to_dt - from_dt).total_seconds() / 60
        if calls is not None:
            calls.append((match.group(1), match.group(2)))
        if fail_above_minutes is not None and minutes > fail_above_minutes:
            raise ElasticRequestError("HTTP 502", retryable=True)
        lines = ["timestamp,host,app_name,level,message"]
        for index in range(rows_per_chunk):
            stamp = (from_dt + timedelta(seconds=index)).isoformat(timespec="milliseconds")
            lines.append(f"{stamp},acss201,solar-acs,INFO, [thread] logger - msg")
        return "\n".join(lines) + "\n"

    return executor


class ElasticCredentialsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {key: os.environ.get(key) for key in ("ELASTIC_PASS", "ELASTIC_USER")}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_missing_password_raises(self) -> None:
        os.environ.pop("ELASTIC_PASS", None)
        with self.assertRaises(ElasticConfigError):
            get_credentials()

    def test_default_user(self) -> None:
        os.environ["ELASTIC_PASS"] = "secret"
        os.environ.pop("ELASTIC_USER", None)
        credentials = get_credentials()
        self.assertEqual(credentials.user, "solar")
        self.assertEqual(credentials.password, "secret")


class ElasticDownloadTest(unittest.TestCase):
    def _future_now(self) -> datetime:
        return datetime(2030, 1, 1, tzinfo=elastic_logs._tz())

    def test_full_day_collects_all_chunks(self) -> None:
        executor = _make_executor()
        result = download_day("2026-06-23", now=self._future_now(), executor=executor)
        self.assertEqual(result.row_count, 48)
        self.assertFalse(result.partial)
        first_line = result.content.splitlines()[0]
        self.assertTrue(first_line.startswith("2026-06-23 00:00:00.000 INFO [acss201]"))

    def test_content_is_sorted_and_parser_compatible(self) -> None:
        from app.parsers.acs_log_parser import parse_log_content

        executor = _make_executor(rows_per_chunk=2)
        result = download_day("2026-06-23", now=self._future_now(), executor=executor)
        lines = result.content.splitlines()
        self.assertEqual(lines, sorted(lines))
        rows = parse_log_content("solar-acs.2026-06-23.log", result.content)
        self.assertIsInstance(rows, list)

    def test_split_on_retryable_error(self) -> None:
        calls: list[tuple[str, str]] = []
        executor = _make_executor(fail_above_minutes=20, calls=calls)
        result = download_day("2026-06-23", now=self._future_now(), executor=executor)
        self.assertEqual(result.row_count, 96)
        self.assertTrue(any(call[0].endswith(":15:00.000+03:00") for call in calls))

    def test_non_retryable_error_propagates(self) -> None:
        def executor(body: str) -> str:
            raise ElasticRequestError("HTTP 401", retryable=False)

        with self.assertRaises(ElasticRequestError):
            download_day("2026-06-23", now=self._future_now(), executor=executor)

    def test_today_is_capped_to_now(self) -> None:
        tz = elastic_logs._tz()
        today = datetime.now(tz).date()
        now = datetime.combine(today, datetime.min.time(), tzinfo=tz) + timedelta(hours=2)
        executor = _make_executor()
        result = download_day(today.isoformat(), now=now, executor=executor)
        self.assertTrue(result.partial)
        self.assertEqual(result.row_count, 4)

    def test_skip_download_for_downloaded_closed_day(self) -> None:
        self.assertTrue(
            should_skip_download("2026-06-20", download_complete=True, today="2026-06-24")
        )

    def test_no_skip_when_not_downloaded(self) -> None:
        self.assertFalse(
            should_skip_download("2026-06-20", download_complete=False, today="2026-06-24")
        )

    def test_no_skip_for_today_even_if_downloaded(self) -> None:
        self.assertFalse(
            should_skip_download("2026-06-24", download_complete=True, today="2026-06-24")
        )

    def test_no_skip_for_partial_download(self) -> None:
        self.assertFalse(
            should_skip_download("2026-06-20", download_complete=False, today="2026-06-24")
        )

    def test_plan_download_redownloads_partial_days(self) -> None:
        to_download, skipped, _future = plan_download_dates(
            "2026-06-20",
            "2026-06-22",
            today="2026-06-25",
            downloaded={"2026-06-21"},
        )
        self.assertEqual(to_download, ["2026-06-20", "2026-06-22"])
        self.assertEqual(skipped, ["2026-06-21"])

    def test_download_can_be_cancelled(self) -> None:
        calls = {"count": 0}

        def executor(body: str) -> str:
            calls["count"] += 1
            if calls["count"] > 2:
                return _make_executor()(body)
            return _make_executor()(body)

        cancelled = {"stop": False}

        def should_cancel() -> bool:
            return cancelled["stop"]

        def progress(done: int, total: int, label: str) -> None:
            if done >= 30:
                cancelled["stop"] = True

        with self.assertRaises(elastic_logs.ElasticDownloadCancelled):
            download_day(
                "2026-06-23",
                now=self._future_now(),
                executor=executor,
                progress=progress,
                should_cancel=should_cancel,
            )

    def test_iter_days_inclusive(self) -> None:
        self.assertEqual(
            iter_days("2026-06-20", "2026-06-23"),
            ["2026-06-20", "2026-06-21", "2026-06-22", "2026-06-23"],
        )

    def test_iter_days_handles_reversed_range(self) -> None:
        self.assertEqual(iter_days("2026-06-23", "2026-06-20"), iter_days("2026-06-20", "2026-06-23"))

    def test_plan_download_skips_existing_interval(self) -> None:
        to_download, skipped, future = plan_download_dates(
            "2026-06-20",
            "2026-06-24",
            today="2026-06-25",
            downloaded={"2026-06-21", "2026-06-22"},
        )
        self.assertEqual(to_download, ["2026-06-20", "2026-06-23", "2026-06-24"])
        self.assertEqual(skipped, ["2026-06-21", "2026-06-22"])
        self.assertEqual(future, [])

    def test_plan_download_excludes_future_but_keeps_today(self) -> None:
        to_download, skipped, future = plan_download_dates(
            "2026-06-23",
            "2026-06-26",
            today="2026-06-24",
            downloaded={"2026-06-23"},
        )
        self.assertEqual(to_download, ["2026-06-24"])
        self.assertEqual(skipped, ["2026-06-23"])
        self.assertEqual(future, ["2026-06-25", "2026-06-26"])

    def test_plan_download_today_redownloads_even_if_present(self) -> None:
        to_download, skipped, _future = plan_download_dates(
            "2026-06-24",
            "2026-06-24",
            today="2026-06-24",
            downloaded={"2026-06-24"},
        )
        self.assertEqual(to_download, ["2026-06-24"])
        self.assertEqual(skipped, [])

    def test_resolve_day_bounds_future_day_raises(self) -> None:
        tz = elastic_logs._tz()
        today = datetime.now(tz).date()
        future = (today + timedelta(days=2)).isoformat()
        now = datetime.combine(today, datetime.min.time(), tzinfo=tz) + timedelta(hours=5)
        with self.assertRaises(elastic_logs.ElasticError):
            resolve_day_bounds(future, now=now)


class ElasticTlsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            key: os.environ.get(key)
            for key in ("ELASTIC_VERIFY_TLS", "ELASTIC_CA_BUNDLE")
        }

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_verify_off_by_default(self) -> None:
        os.environ.pop("ELASTIC_VERIFY_TLS", None)
        os.environ.pop("ELASTIC_CA_BUNDLE", None)
        self.assertFalse(elastic_logs.verify_tls_enabled())
        context = elastic_logs.build_ssl_context()
        self.assertFalse(context.check_hostname)
        self.assertEqual(context.verify_mode, elastic_logs.ssl.CERT_NONE)

    def test_verify_can_be_enabled(self) -> None:
        os.environ.pop("ELASTIC_CA_BUNDLE", None)
        os.environ["ELASTIC_VERIFY_TLS"] = "1"
        self.assertTrue(elastic_logs.verify_tls_enabled())
        context = elastic_logs.build_ssl_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, elastic_logs.ssl.CERT_REQUIRED)

    def test_ca_bundle_turns_verification_on(self) -> None:
        os.environ.pop("ELASTIC_VERIFY_TLS", None)
        os.environ["ELASTIC_CA_BUNDLE"] = "C:/certs/corp-ca.pem"
        self.assertTrue(elastic_logs.verify_tls_enabled())


CSV_BODY = "timestamp,host,app_name,level,message\n"


class _CsvHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or 0)
        self.rfile.read(length)
        body = CSV_BODY.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # noqa: A002
        return


def _make_self_signed(cert_dir: Path) -> tuple[Path, Path]:
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path), "-out", str(cert_path),
            "-days", "3650", "-nodes", "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return cert_path, key_path


class ElasticExecutorTlsIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("openssl") is None:
            self.skipTest("openssl not available")
        self._tmp = tempfile.TemporaryDirectory()
        try:
            self._cert, self._key = _make_self_signed(Path(self._tmp.name))
        except (subprocess.CalledProcessError, OSError):
            self._tmp.cleanup()
            self.skipTest("could not generate self-signed certificate")

        self._saved = {
            key: os.environ.get(key)
            for key in (
                "ELASTIC_PASS",
                "ELASTIC_URL",
                "ELASTIC_VERIFY_TLS",
                "ELASTIC_CA_BUNDLE",
            )
        }
        os.environ["ELASTIC_PASS"] = "secret"
        for key in ("ELASTIC_VERIFY_TLS", "ELASTIC_CA_BUNDLE"):
            os.environ.pop(key, None)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self._cert), str(self._key))
        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _CsvHandler)
        self._server.socket = context.wrap_socket(self._server.socket, server_side=True)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def tearDown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def test_default_connects_without_verification(self) -> None:
        os.environ["ELASTIC_URL"] = f"https://127.0.0.1:{self._port}/"
        result = elastic_logs._default_executor("{}")
        self.assertIn("timestamp", result)

    def test_verify_enabled_without_ca_fails(self) -> None:
        os.environ["ELASTIC_URL"] = f"https://127.0.0.1:{self._port}/"
        os.environ["ELASTIC_VERIFY_TLS"] = "1"
        with self.assertRaises(elastic_logs.ElasticRequestError):
            elastic_logs._default_executor("{}")

    def test_verify_with_ca_bundle_succeeds(self) -> None:
        os.environ["ELASTIC_URL"] = f"https://127.0.0.1:{self._port}/"
        os.environ["ELASTIC_CA_BUNDLE"] = str(self._cert)
        result = elastic_logs._default_executor("{}")
        self.assertIn("timestamp", result)


def _count_executor(*, big_count, small_count, big_threshold_minutes=2):
    def executor(body: str) -> str:
        data = json.loads(body)
        match = _RANGE_RE.search(data["query"])
        from_dt = datetime.fromisoformat(match.group(1))
        to_dt = datetime.fromisoformat(match.group(2))
        minutes = (to_dt - from_dt).total_seconds() / 60
        count = big_count if minutes >= big_threshold_minutes else small_count
        lines = ["timestamp,host,app_name,level,message"]
        for index in range(count):
            stamp = (from_dt + timedelta(seconds=index)).isoformat(timespec="milliseconds")
            lines.append(f"{stamp},acss201,solar-acs,INFO, [thread] logger - msg")
        return "\n".join(lines) + "\n"

    return executor


class ElasticTruncationTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved_limit = elastic_logs.QUERY_LIMIT
        self._saved_dropped = os.environ.get("ELASTIC_MAX_DROPPED")

    def tearDown(self) -> None:
        elastic_logs.QUERY_LIMIT = self._saved_limit
        if self._saved_dropped is None:
            os.environ.pop("ELASTIC_MAX_DROPPED", None)
        else:
            os.environ["ELASTIC_MAX_DROPPED"] = self._saved_dropped

    def _partial_now(self, minutes: int) -> tuple[str, datetime]:
        tz = elastic_logs._tz()
        today = datetime.now(tz).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
        return today.isoformat(), start + timedelta(minutes=minutes)

    def test_limit_chunk_splits_then_succeeds(self) -> None:
        elastic_logs.QUERY_LIMIT = 5
        log_date, now = self._partial_now(4)
        executor = _count_executor(big_count=5, small_count=2)
        result = download_day(log_date, now=now, executor=executor)
        self.assertEqual(result.row_count, 8)

    def test_min_chunk_at_limit_fails_day(self) -> None:
        elastic_logs.QUERY_LIMIT = 5
        log_date, now = self._partial_now(4)
        executor = _count_executor(big_count=5, small_count=5)
        with self.assertRaises(elastic_logs.ElasticError):
            download_day(log_date, now=now, executor=executor)

    def test_invalid_timestamps_counted(self) -> None:
        log_date, now = self._partial_now(2)

        def executor(body: str) -> str:
            data = json.loads(body)
            match = _RANGE_RE.search(data["query"])
            from_dt = datetime.fromisoformat(match.group(1))
            good = (from_dt).isoformat(timespec="milliseconds")
            return (
                "timestamp,host,app_name,level,message\n"
                f"{good},acss201,solar-acs,INFO, [t] l - ok\n"
                ",acss201,solar-acs,INFO, [t] l - broken\n"
            )

        result = download_day(log_date, now=now, executor=executor)
        self.assertEqual(result.row_count, 1)
        self.assertEqual(result.dropped_count, 1)

    def test_dropped_above_threshold_fails(self) -> None:
        os.environ["ELASTIC_MAX_DROPPED"] = "0"
        log_date, now = self._partial_now(2)

        def executor(body: str) -> str:
            return (
                "timestamp,host,app_name,level,message\n"
                ",acss201,solar-acs,INFO, [t] l - broken\n"
            )

        with self.assertRaises(elastic_logs.ElasticError):
            download_day(log_date, now=now, executor=executor)


if __name__ == "__main__":
    unittest.main()
