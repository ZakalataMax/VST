import os
import tempfile
import unittest
from pathlib import Path

from app.services import log_storage

ELASTIC_LINE = (
    "2026-06-23 00:00:01.783 INFO [acss202]  [qtp-1] "
    "c.s.s.i.a.s.AcsCoreComponentImpl - Polling known nodes process has started."
)


class ElasticStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._saved_log = os.environ.get("LOG_STORAGE_DIR")
        os.environ["LOG_STORAGE_DIR"] = str(Path(self._tmp.name) / "logs")

    def tearDown(self) -> None:
        if self._saved_log is None:
            os.environ.pop("LOG_STORAGE_DIR", None)
        else:
            os.environ["LOG_STORAGE_DIR"] = self._saved_log
        self._tmp.cleanup()

    def test_save_and_read_elastic_day(self) -> None:
        record = log_storage.save_elastic_log(
            "2026-06-23",
            ELASTIC_LINE + "\n",
            partial=False,
            row_count=1,
            min_datetime="2026-06-23 00:00:01.783",
            max_datetime="2026-06-23 00:00:01.783",
        )
        self.assertEqual(record["source"], "elastic")
        self.assertTrue(log_storage.has_elastic_log("2026-06-23"))

        days = log_storage.list_log_days()
        self.assertEqual(len(days), 1)
        self.assertTrue(days[0]["elastic"])
        self.assertTrue(days[0]["complete"])

        files = log_storage.list_log_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["acsNode"], "elastic")

        stored = log_storage.read_day_for_parse("2026-06-23")
        self.assertEqual(len(stored), 1)
        self.assertIn("Polling known nodes", stored[0][1])

    def test_partial_flag_not_complete(self) -> None:
        log_storage.save_elastic_log("2026-06-24", ELASTIC_LINE + "\n", partial=True)
        self.assertTrue(log_storage.has_elastic_log("2026-06-24"))
        self.assertFalse(log_storage.elastic_download_complete("2026-06-24"))

    def test_full_day_is_complete(self) -> None:
        log_storage.save_elastic_log("2026-06-25", ELASTIC_LINE + "\n", partial=False)
        self.assertTrue(log_storage.elastic_download_complete("2026-06-25"))

    def test_legacy_acs_pair_still_reads(self) -> None:
        log_storage.save_upload("ACS1_common.2026-06-15.0.log", b"acs1 content\n")
        log_storage.save_upload("ACS2_common.2026-06-15.0.log", b"acs2 content\n")
        stored = log_storage.read_day_for_parse("2026-06-15")
        self.assertEqual(len(stored), 2)

        days = log_storage.list_log_days()
        day = next(item for item in days if item["date"] == "2026-06-15")
        self.assertTrue(day["complete"])
        self.assertFalse(day["elastic"])

    def test_legacy_missing_node_raises(self) -> None:
        log_storage.save_upload("ACS1_common.2026-06-16.0.log", b"acs1 only\n")
        with self.assertRaises(ValueError):
            log_storage.read_day_for_parse("2026-06-16")

    def test_elastic_preferred_when_both_present(self) -> None:
        log_storage.save_upload("ACS1_common.2026-06-17.0.log", b"acs1\n")
        log_storage.save_upload("ACS2_common.2026-06-17.0.log", b"acs2\n")
        log_storage.save_elastic_log("2026-06-17", ELASTIC_LINE + "\n", partial=False)
        stored = log_storage.read_day_for_parse("2026-06-17")
        self.assertEqual(len(stored), 1)
        self.assertIn("Polling known nodes", stored[0][1])


if __name__ == "__main__":
    unittest.main()
