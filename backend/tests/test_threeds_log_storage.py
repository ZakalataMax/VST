import os
import tempfile
import unittest
from pathlib import Path

from app.threeds import log_storage

LOG_LINE = (
    "2026-06-23 10:14:27.658 INFO [3dss201]  [DefaultDispatcher-worker-4] "
    "c.s.s.i.t.s.s.ThreeDsServerCoreComponentImpl - Incoming message: "
    '[{"threeDSServerTransID":"t1","acsTransID":"a1","messageType":"CRes"}].'
)


class ThreeDsLogStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = os.environ.get("THREEDS_LOG_STORAGE_DIR")
        os.environ["THREEDS_LOG_STORAGE_DIR"] = str(Path(self._tmp.name) / "logs_3ds")

    def tearDown(self) -> None:
        if self._saved is None:
            os.environ.pop("THREEDS_LOG_STORAGE_DIR", None)
        else:
            os.environ["THREEDS_LOG_STORAGE_DIR"] = self._saved
        self._tmp.cleanup()

    def test_save_and_read_round_trip(self) -> None:
        record = log_storage.save_elastic_log(
            "2026-06-23",
            LOG_LINE + "\n",
            partial=False,
            row_count=1,
            min_datetime="2026-06-23 10:14:27.658",
            max_datetime="2026-06-23 10:14:27.658",
        )
        self.assertEqual(record["logDate"], "2026-06-23")
        self.assertTrue(log_storage.has_elastic_log("2026-06-23"))
        self.assertTrue(log_storage.elastic_download_complete("2026-06-23"))

        content = log_storage.read_log_content("2026-06-23")
        self.assertIn("ThreeDsServerCoreComponentImpl", content)

        days = log_storage.list_log_days()
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0]["date"], "2026-06-23")
        self.assertEqual(days[0]["rowCount"], 1)
        self.assertFalse(days[0]["partial"])

    def test_partial_flag_not_complete(self) -> None:
        log_storage.save_elastic_log("2026-06-24", LOG_LINE + "\n", partial=True)
        self.assertFalse(log_storage.elastic_download_complete("2026-06-24"))

    def test_read_missing_day_raises(self) -> None:
        with self.assertRaises(ValueError):
            log_storage.read_log_content("2026-01-01")

    def test_delete_removes_day(self) -> None:
        log_storage.save_elastic_log("2026-06-25", LOG_LINE + "\n", partial=False)
        self.assertTrue(log_storage.has_elastic_log("2026-06-25"))
        log_storage.delete_log_day("2026-06-25")
        self.assertFalse(log_storage.has_elastic_log("2026-06-25"))
        self.assertEqual(log_storage.list_log_days(), [])


if __name__ == "__main__":
    unittest.main()
