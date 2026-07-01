import os
import unittest

from app.parsers.acs_log_parser import (
    ParseDiagnostics,
    max_dropped_lines,
    parse_log_content,
)

PREFIX = "2026-06-20 10:00:0"

VALID_OOB = (
    f'{PREFIX}0.000 INFO [acss201] L - Incoming message: '
    '[OobResultRequest{"tdssTxnId":"t1","status":"01"}].'
)
BAD_OOB = (
    f'{PREFIX}1.000 INFO [acss201] L - Incoming message: '
    "[OobResultRequest{not valid json}]."
)
BAD_ARRAY = (
    f'{PREFIX}2.000 INFO [acss201] L - Incoming message: [{{broken json}}].'
)


class ParserDroppedTest(unittest.TestCase):
    def test_malformed_oob_counted_not_crashing(self) -> None:
        diagnostics = ParseDiagnostics()
        rows = parse_log_content("t.log", BAD_OOB, diagnostics=diagnostics)
        self.assertEqual(rows, [])
        self.assertEqual(diagnostics.dropped_count, 1)
        self.assertTrue(diagnostics.samples)

    def test_valid_oob_has_no_drop(self) -> None:
        diagnostics = ParseDiagnostics()
        rows = parse_log_content("t.log", VALID_OOB, diagnostics=diagnostics)
        self.assertEqual(len(rows), 1)
        self.assertEqual(diagnostics.dropped_count, 0)

    def test_malformed_json_array_counted(self) -> None:
        diagnostics = ParseDiagnostics()
        rows = parse_log_content("t.log", BAD_ARRAY, diagnostics=diagnostics)
        self.assertEqual(rows, [])
        self.assertEqual(diagnostics.dropped_count, 1)

    def test_diagnostics_optional_keeps_list_api(self) -> None:
        rows = parse_log_content("t.log", BAD_OOB)
        self.assertEqual(rows, [])

    def test_max_dropped_lines_env_override(self) -> None:
        saved = os.environ.get("PARSER_MAX_DROPPED")
        try:
            os.environ["PARSER_MAX_DROPPED"] = "5"
            self.assertEqual(max_dropped_lines(), 5)
            os.environ["PARSER_MAX_DROPPED"] = "not-a-number"
            self.assertEqual(max_dropped_lines(), 100)
        finally:
            if saved is None:
                os.environ.pop("PARSER_MAX_DROPPED", None)
            else:
                os.environ["PARSER_MAX_DROPPED"] = saved


if __name__ == "__main__":
    unittest.main()
