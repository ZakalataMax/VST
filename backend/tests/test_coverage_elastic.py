import unittest

from desktop.coverage_utils import (
    STATUS_MISSING,
    STATUS_PARSED,
    STATUS_PARTIAL,
    STATUS_READY,
    build_coverage_days,
    coverage_dots,
    day_has_logs,
    get_day_coverage_status,
    resolve_day_status,
)


class CoverageElasticTest(unittest.TestCase):
    def test_day_has_logs(self) -> None:
        self.assertTrue(day_has_logs({"elastic": True}))
        self.assertTrue(day_has_logs({"acs1": True, "acs2": True}))
        self.assertFalse(day_has_logs({"acs1": True}))
        self.assertFalse(day_has_logs({}))

    def test_coverage_dots_elastic(self) -> None:
        self.assertEqual(coverage_dots({"elastic": True}), "EL")
        self.assertEqual(coverage_dots({"acs1": True, "acs2": False}), "●○")

    def test_elastic_ready_without_pair(self) -> None:
        day = {"date": "2026-06-23", "log_day": {"elastic": True}, "csv_day": None}
        self.assertEqual(resolve_day_status(day), STATUS_READY)

    def test_elastic_full_day_parsed(self) -> None:
        log_day = {"elastic": True}
        csv_day = {"fullDay": True, "rowCount": 100}
        complete, _ = get_day_coverage_status(log_day, csv_day)
        self.assertTrue(complete)

    def test_elastic_partial_day(self) -> None:
        day = {
            "date": "2026-06-24",
            "log_day": {"elastic": True},
            "csv_day": {"fullDay": False, "rowCount": 10},
            "complete": False,
        }
        self.assertEqual(resolve_day_status(day), STATUS_PARTIAL)

    def test_legacy_missing_node(self) -> None:
        day = {"date": "2026-06-16", "log_day": {"acs1": True, "acs2": False}, "csv_day": None}
        self.assertEqual(resolve_day_status(day), STATUS_MISSING)

    def test_build_coverage_days_marks_elastic(self) -> None:
        log_days = [{"date": "2026-06-23", "acs1": False, "acs2": False, "elastic": True, "complete": True}]
        csv_days = [
            {"date": "2026-06-23", "rowCount": 100, "minDateTime": "", "maxDateTime": "", "fullDay": True}
        ]
        days = build_coverage_days([], log_days, csv_days)
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0]["status"], STATUS_PARSED)
        self.assertEqual(days[0]["coverage_dots"], "EL")


if __name__ == "__main__":
    unittest.main()
