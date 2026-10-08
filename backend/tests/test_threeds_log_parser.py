import unittest

from app.threeds.parsers.threeds_log_parser import (
    ParseDiagnostics,
    parse_log_content,
    parse_log_files,
)

PREFIX = "2026-10-06 00:05:4"

AREQ_LINE = (
    f'{PREFIX}2.629 INFO [3dss201]  [w] c.s.s.i.t.s.s.ThreeDsServerCoreComponentImpl - '
    'Outgoing message: [{"messageType":"AReq","messageVersion":"2.2.0",'
    '"threeDSServerTransID":"t1","acctNumber":"486636****9640","merchantName":"CARTERS2",'
    '"purchaseAmount":"68400"}].'
)
ARES_LINE = (
    f'{PREFIX}4.158 INFO [3dss201]  [w] c.s.s.i.t.s.s.ThreeDsServerCoreComponentImpl - '
    'Incoming message: [{"messageType":"ARes","threeDSServerTransID":"t1",'
    '"acsTransID":"a1","transStatus":"C"}].'
)
RREQ_LINE = (
    f'{PREFIX}8.125 INFO [3dss202]  [w] c.s.s.i.t.s.s.ThreeDsServerCoreComponentImpl - '
    'Incoming message: [{"messageCategory":"01","messageType":"RReq",'
    '"threeDSServerTransID":"t1","transStatus":"N","transStatusReason":"14"}].'
)
RECEIVED_RREQ_LINE = (
    f'{PREFIX}8.125 INFO [3dss202]  [w] c.s.s.i.t.s.s.ThreeDsServerCoreComponentImpl - '
    "Received RReq for txn[abc123] with status: [DENIED] / [TXN_TIMED_OUT_AT_ACS]."
)
RECEIVED_RREQ_SUCCESS_LINE = (
    f'{PREFIX}8.125 INFO [3dss202]  [w] c.s.s.i.t.s.s.ThreeDsServerCoreComponentImpl - '
    "Received RReq for txn[abc123] with status: [SUCCESS] / [null]."
)
METHOD_EXPIRED_LINE = (
    f'{PREFIX}9.520 INFO [3dss202]  [w] c.s.s.i.t.s.s.ThreeDsServerCoreComponentImpl - '
    "slr.ipa.tdss.log.3ds_method_expired: [abc123]"
)
NOISE_LINE = (
    f'{PREFIX}0.034 INFO [3dss201]  [w] c.s.s.i.n.r.r.s.AppNodesRuntimeRegistryImpl - '
    "Polling known nodes process has started."
)
BAD_JSON_LINE = (
    f'{PREFIX}1.000 INFO [3dss201]  [w] c.s.s.i.t.s.s.ThreeDsServerCoreComponentImpl - '
    "Outgoing message: [{broken json}]."
)


class ThreeDsParserTest(unittest.TestCase):
    def test_areq_json_fields_mapped(self) -> None:
        rows = parse_log_content("t.log", AREQ_LINE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.message_type, "AReq")
        self.assertEqual(row.message_direction, "Out")
        self.assertEqual(row.three_ds_server_trans_id, "t1")
        self.assertEqual(row.acct_number, "486636****9640")
        self.assertEqual(row.merchant_name, "CARTERS2")
        self.assertEqual(row.purchase_amount, "68400")

    def test_ares_json_fields_mapped(self) -> None:
        rows = parse_log_content("t.log", ARES_LINE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.message_type, "ARes")
        self.assertEqual(row.message_direction, "In")
        self.assertEqual(row.acs_trans_id, "a1")
        self.assertEqual(row.trans_status, "C")

    def test_rreq_json_parses_despite_message_type_not_first_key(self) -> None:
        rows = parse_log_content("t.log", RREQ_LINE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.message_type, "RReq")
        self.assertEqual(row.trans_status, "N")
        self.assertEqual(row.trans_status_reason, "14")

    def test_received_rreq_status_line_becomes_synthetic_row(self) -> None:
        rows = parse_log_content("t.log", RECEIVED_RREQ_LINE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.message_type, "RReqResult")
        self.assertEqual(row.three_ds_server_trans_id, "abc123")
        self.assertEqual(row.rreq_result_status, "DENIED")
        self.assertEqual(row.rreq_result_reason, "TXN_TIMED_OUT_AT_ACS")

    def test_received_rreq_success_with_null_reason(self) -> None:
        rows = parse_log_content("t.log", RECEIVED_RREQ_SUCCESS_LINE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].rreq_result_status, "SUCCESS")
        self.assertEqual(rows[0].rreq_result_reason, "null")

    def test_method_expired_line_becomes_synthetic_row(self) -> None:
        rows = parse_log_content("t.log", METHOD_EXPIRED_LINE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].message_type, "MethodExpired")
        self.assertEqual(rows[0].three_ds_server_trans_id, "abc123")

    def test_noise_line_produces_no_rows(self) -> None:
        rows = parse_log_content("t.log", NOISE_LINE)
        self.assertEqual(rows, [])

    def test_malformed_json_counted_not_crashing(self) -> None:
        diagnostics = ParseDiagnostics()
        rows = parse_log_content("t.log", BAD_JSON_LINE, diagnostics=diagnostics)
        self.assertEqual(rows, [])
        self.assertEqual(diagnostics.dropped_count, 1)
        self.assertTrue(diagnostics.samples)

    def test_parse_log_files_sorts_by_message_sort_order(self) -> None:
        content = "\n".join(
            [RECEIVED_RREQ_LINE, RREQ_LINE, ARES_LINE, AREQ_LINE, METHOD_EXPIRED_LINE]
        )
        rows = parse_log_files([("t.log", content)])
        types = [row.message_type for row in rows]
        # AReq (42.629) < ARes (44.158) < RReq/RReqResult (tied at 48.125, RReq sorts
        # first per MESSAGE_SORT_ORDER) < MethodExpired (49.520).
        self.assertEqual(types, ["AReq", "ARes", "RReq", "RReqResult", "MethodExpired"])


if __name__ == "__main__":
    unittest.main()
