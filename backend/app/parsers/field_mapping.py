from __future__ import annotations

from typing import Any

from app.parsers.models import MessageRow

JSON_FIELD_MAP = {
    "threeDSServerTransID": "three_ds_server_trans_id",
    "transType": "trans_type",
    "transStatus": "trans_status",
    "transStatusReason": "trans_status_reason",
    "interactionCounter": "interaction_counter",
    "authenticationMethod": "authentication_method",
    "authenticationType": "authentication_type",
    "eci": "eci",
    "resultsStatus": "results_status",
    "acsCounterAtoS": "acs_counter_atos",
    "challengeCompletionInd": "challenge_completion_ind",
    "challengeCancel": "challenge_cancel",
    "threeDSServerOperatorID": "three_ds_server_operator_id",
    "acquirerMerchantID": "acquirer_merchant_id",
    "merchantName": "merchant_name",
    "acctNumber": "acct_number",
    "acquirerBIN": "acquirer_bin",
    "browserIP": "browser_ip",
    "errorCode": "error_code",
}


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def apply_json_payload(row: MessageRow, payload: dict[str, Any]) -> None:
    message_type = payload.get("messageType")
    if message_type:
        row.message_type = _as_str(message_type)

    trans_id = payload.get("threeDSServerTransID") or payload.get("tdssTxnId")
    if trans_id:
        row.three_ds_server_trans_id = _as_str(trans_id)

    for json_key, attr in JSON_FIELD_MAP.items():
        if json_key in payload and payload[json_key] is not None:
            setattr(row, attr, _as_str(payload[json_key]))
