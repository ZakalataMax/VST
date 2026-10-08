from __future__ import annotations

from typing import Any

from app.threeds.parsers.models import ThreeDsMessageRow

JSON_FIELD_MAP = {
    "threeDSServerTransID": "three_ds_server_trans_id",
    "acsTransID": "acs_trans_id",
    "dsTransID": "ds_trans_id",
    "messageVersion": "message_version",
    "messageCategory": "message_category",
    "threeDSCompInd": "three_ds_comp_ind",
    "threeDSRequestorAuthenticationInd": "three_ds_requestor_authentication_ind",
    "threeDSRequestorID": "three_ds_requestor_id",
    "threeDSRequestorName": "three_ds_requestor_name",
    "threeDSRequestorURL": "three_ds_requestor_url",
    "threeDSServerRefNumber": "three_ds_server_ref_number",
    "threeDSServerOperatorID": "three_ds_server_operator_id",
    "threeDSServerURL": "three_ds_server_url",
    "acquirerBIN": "acquirer_bin",
    "acquirerMerchantID": "acquirer_merchant_id",
    "browserAcceptHeader": "browser_accept_header",
    "browserJavaEnabled": "browser_java_enabled",
    "browserJavascriptEnabled": "browser_javascript_enabled",
    "browserLanguage": "browser_language",
    "browserColorDepth": "browser_color_depth",
    "browserScreenHeight": "browser_screen_height",
    "browserScreenWidth": "browser_screen_width",
    "browserTZ": "browser_tz",
    "browserUserAgent": "browser_user_agent",
    "cardExpiryDate": "card_expiry_date",
    "acctNumber": "acct_number",
    "deviceChannel": "device_channel",
    "mcc": "mcc",
    "merchantCountryCode": "merchant_country_code",
    "merchantName": "merchant_name",
    "notificationURL": "notification_url",
    "purchaseAmount": "purchase_amount",
    "purchaseCurrency": "purchase_currency",
    "purchaseExponent": "purchase_exponent",
    "purchaseDate": "purchase_date",
    "transType": "trans_type",
    "acsOperatorID": "acs_operator_id",
    "acsReferenceNumber": "acs_reference_number",
    "dsReferenceNumber": "ds_reference_number",
    "acsChallengeMandated": "acs_challenge_mandated",
    "authenticationType": "authentication_type",
    "authenticationValue": "authentication_value",
    "acsURL": "acs_url",
    "transStatus": "trans_status",
    "transStatusReason": "trans_status_reason",
    "eci": "eci",
    "challengeWindowSize": "challenge_window_size",
    "interactionCounter": "interaction_counter",
    "challengeCancel": "challenge_cancel",
    "resultsStatus": "results_status",
    "serialNum": "serial_num",
    "dsStartProtocolVersion": "ds_start_protocol_version",
    "dsEndProtocolVersion": "ds_end_protocol_version",
    "errorCode": "error_code",
    "errorComponent": "error_component",
    "errorDescription": "error_description",
    "errorDetail": "error_detail",
    "errorMessageType": "error_message_type",
}


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return ""
    return str(value)


def apply_json_payload(row: ThreeDsMessageRow, payload: dict[str, Any]) -> None:
    message_type = payload.get("messageType")
    if message_type:
        row.message_type = _as_str(message_type)

    for json_key, attr in JSON_FIELD_MAP.items():
        if json_key in payload and payload[json_key] is not None:
            setattr(row, attr, _as_str(payload[json_key]))
