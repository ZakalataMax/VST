import json
import os
import re
import unittest
from datetime import datetime, timedelta

from app.common import elastic_logs
from app.common.elastic_logs import build_query_body, download_day
from app.threeds.elastic_config import THREEDS_SOURCE

_RANGE_RE = re.compile(r">= '([^']+)' AND timestamp < '([^']+)'")


def _make_executor(rows_per_chunk=1):
    def executor(body: str) -> str:
        data = json.loads(body)
        match = _RANGE_RE.search(data["query"])
        from_dt = datetime.fromisoformat(match.group(1))
        lines = ["timestamp,host,app_name,level,message"]
        for index in range(rows_per_chunk):
            stamp = (from_dt + timedelta(seconds=index)).isoformat(timespec="milliseconds")
            lines.append(f"{stamp},3dss201,solar-3ds-server,INFO, [thread] logger - msg")
        return "\n".join(lines) + "\n"

    return executor


class ThreeDsQueryBodyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.get("ELASTIC_3DS_APP_NAME")

    def tearDown(self) -> None:
        if self._saved is None:
            os.environ.pop("ELASTIC_3DS_APP_NAME", None)
        else:
            os.environ["ELASTIC_3DS_APP_NAME"] = self._saved

    def test_default_app_name_and_hosts(self) -> None:
        os.environ.pop("ELASTIC_3DS_APP_NAME", None)
        from_dt = datetime(2026, 6, 23)
        to_dt = from_dt + timedelta(minutes=30)
        body = json.loads(build_query_body(from_dt, to_dt, THREEDS_SOURCE))
        self.assertIn("app_name = 'solar-3ds-server'", body["query"])
        self.assertIn("host IN ('3dss201', '3dss202')", body["query"])

    def test_app_name_env_override(self) -> None:
        os.environ["ELASTIC_3DS_APP_NAME"] = "solar-3ds-server-staging"
        from_dt = datetime(2026, 6, 23)
        to_dt = from_dt + timedelta(minutes=30)
        body = json.loads(build_query_body(from_dt, to_dt, THREEDS_SOURCE))
        self.assertIn("app_name = 'solar-3ds-server-staging'", body["query"])


class ThreeDsDownloadDayTest(unittest.TestCase):
    def _future_now(self) -> datetime:
        return datetime(2030, 1, 1, tzinfo=elastic_logs._tz())

    def test_full_day_collects_all_chunks(self) -> None:
        executor = _make_executor()
        result = download_day(
            "2026-06-23", THREEDS_SOURCE, now=self._future_now(), executor=executor
        )
        self.assertEqual(result.row_count, 48)
        self.assertFalse(result.partial)
        first_line = result.content.splitlines()[0]
        self.assertTrue(first_line.startswith("2026-06-23 00:00:00.000 INFO [3dss201]"))


if __name__ == "__main__":
    unittest.main()
