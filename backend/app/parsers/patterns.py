import re

TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")

INCOMING_MESSAGE_PAYLOAD_RE = re.compile(r"Incoming message: \[(.+)\]\.\s*$")
OUTGOING_MESSAGE_PAYLOAD_RE = re.compile(r"Outgoing message: \[(.+)\]\.\s*$")

OOB_INIT_IN_RE = re.compile(r"Incoming message: \[(OobInitResponse)(\{.*\})\]\.?\s*$")
OOB_INIT_OUT_RE = re.compile(r"Outgoing message: \[(OobInitRequest)(\{.*\})\]\.?\s*$")
OOB_RESULT_IN_RE = re.compile(r"Incoming message: \[(OobResultRequest)(\{.*\})\]\.?\s*$")
OOB_RESULT_OUT_RE = re.compile(r"Outgoing message: \[(OobResultResponse)(\{.*\})\]\.?\s*$")

CHALLENGE_ANSWER_RE = re.compile(
    r"Incoming message: \[ChallengeAnswerRequest: \{([^}]*)\}\]\.?\s*$"
)
CHALLENGE_METHOD_RE = re.compile(
    r"Handling challenge response data for 3DSS txn\[([^\]]+)\], ACS txn\[([^\]]+)\], method\[([^\[]+)\[code='(\d+)'\]\]\."
)
CHALLENGE_SUCCEEDED_RE = re.compile(
    r"Challenge is succeeded \(OK\) for acsTxnId=([^,]+), tdssTxnId=([0-9a-f-]+)\."
)
CHALLENGE_NOT_ACCEPTED_RE = re.compile(
    r"Challenge answer is not accepted for acsTxnId=([^,]+), tdssTxnId=([0-9a-f-]+)\."
)
CHALLENGE_EXPIRING_RE = re.compile(
    r"Challenge is expiring for acsTxnId=([^,]+), tdssTxnId=([0-9a-f-]+)\."
)
# acsTxnId/tdssTxnId values are swapped vs other ACS log lines (see AuthMethodSwitch in acs_log_parser.py).
AUTH_METHOD_SWITCH_RE = re.compile(
    r"Switch auth method for transaction \[acsTxnId=([0-9a-f-]+)\] \[tdssTxnId=([0-9a-f-]+)\] from \[[^\[]+\[code='(\d+)'\]\] to \[[^\[]+\[code='(\d+)'\]\]\."
)
CREQ_STARTED_RE = re.compile(
    r"Started processing of browser challenge request for 3DS Server txn id: \[([0-9a-f-]+)\]\."
)

KV_PAIR_RE = re.compile(r"(\w+)=([^,}]+)")
