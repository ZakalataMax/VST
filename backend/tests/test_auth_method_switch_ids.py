import unittest

from app.parsers.acs_log_parser import parse_log_content

THREE_DS_TXN_ID = "027b8f6f-819f-482d-a552-1e0165e593d1"
ACS_TXN_ID = "8ffa6fd0-2d70-416f-9d05-c30af6b53196"

AUTH_METHOD_SWITCH_LINE = (
    "2026-06-15 02:20:29.399 INFO  [qtp1798217138-64] "
    "c.s.s.i.a.e.AcsChallengeTypeShiftService - "
    "Switch auth method for transaction "
    f"[acsTxnId={THREE_DS_TXN_ID}] [tdssTxnId={ACS_TXN_ID}] "
    "from [OOB_OTHER[code='104']] to [OTP_SMS_N_STATIC_PASSCODE[code='103']]."
)

CHALLENGE_EXPIRING_LINE = (
    "2026-06-15 02:30:29.425 INFO  [pool-4-thread-1] "
    "c.s.s.i.a.s.AcsCoreComponentImpl - "
    f"Challenge is expiring for acsTxnId={ACS_TXN_ID}, tdssTxnId={THREE_DS_TXN_ID}."
)


class AuthMethodSwitchIdMappingTest(unittest.TestCase):
    def test_auth_method_switch_keeps_swapped_acs_log_labels(self) -> None:
        rows = parse_log_content("test.log", AUTH_METHOD_SWITCH_LINE)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row.message_type, "AuthMethodSwitch")
        self.assertEqual(row.three_ds_server_trans_id, THREE_DS_TXN_ID)
        self.assertEqual(row.acs_trans_id, ACS_TXN_ID)
        self.assertEqual(row.auth_method_switch, "104->103")

    def test_challenge_expiring_uses_standard_id_labels(self) -> None:
        rows = parse_log_content("test.log", CHALLENGE_EXPIRING_LINE)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row.message_type, "ChallengeExpiring")
        self.assertEqual(row.three_ds_server_trans_id, THREE_DS_TXN_ID)
        self.assertEqual(row.acs_trans_id, ACS_TXN_ID)


if __name__ == "__main__":
    unittest.main()
