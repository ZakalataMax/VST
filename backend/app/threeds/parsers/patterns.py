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
