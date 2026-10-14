import re

TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")

INCOMING_MESSAGE_PAYLOAD_RE = re.compile(r"Incoming message: \[(.+)\]\.\s*$")
OUTGOING_MESSAGE_PAYLOAD_RE = re.compile(r"Outgoing message: \[(.+)\]\.\s*$")

# "Received RReq for txn[<id>] with status: [SUCCESS|DENIED|REJECTED] / [<REASON>|null]."
# A human-readable restatement of the just-received RReq's transStatus/transStatusReason,
# logged as its own line right before the raw "Incoming message: [...RReq...]" line.
RECEIVED_RREQ_STATUS_RE = re.compile(
    r"Received RReq for txn\[([0-9a-f-]+)\] with status: \[([A-Z]+)\] / \[([A-Za-z0-9_]+|null)\]"
)

# "slr.ipa.tdss.log.3ds_method_expired: [<id>]" - the 3DS Method timer elapsing.
# Fires for ~every transaction - informational, not an error.
METHOD_EXPIRED_RE = re.compile(
    r"slr\.ipa\.tdss\.log\.3ds_method_expired: \[([0-9a-f-]+)\]"
)

# "Received Error message: txn id (acs=[<id>|null], ds=[<id>|null], server=[<id>|null],
# sdk=[<id>|null]), code=[<CODE>], details=[<FIELD>], description=[<TEXT>]."
# The raw "Incoming message: [...Erro...]" JSON often carries only messageType + ids,
# with no errorCode/errorDescription of its own - the actual decoded reason lives only
# in this separate plain-text line, logged right after.
RECEIVED_ERROR_MESSAGE_RE = re.compile(
    r"Received Error message: txn id \(acs=\[([^\]]*)\], ds=\[([^\]]*)\], "
    r"server=\[([^\]]*)\], sdk=\[([^\]]*)\]\), "
    r"code=\[([^\]]*)\], details=\[([^\]]*)\], description=\[([^\]]*)\]"
)
