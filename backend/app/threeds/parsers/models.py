from __future__ import annotations

from dataclasses import dataclass, field

CSV_COLUMNS = [
    "logFile",
    "messageDateTime",
    "messageType",
    "messageDirection",
    "threeDSServerTransID",
    "acsTransID",
    "dsTransID",
    "messageVersion",
    "messageCategory",
    "threeDSCompInd",
    "threeDSRequestorAuthenticationInd",
    "threeDSRequestorID",
    "threeDSRequestorName",
    "threeDSRequestorURL",
    "threeDSServerRefNumber",
    "threeDSServerOperatorID",
    "threeDSServerURL",
    "acquirerBIN",
    "acquirerMerchantID",
    "browserAcceptHeader",
    "browserJavaEnabled",
    "browserJavascriptEnabled",
    "browserLanguage",
    "browserColorDepth",
    "browserScreenHeight",
    "browserScreenWidth",
    "browserTZ",
    "browserUserAgent",
    "browserOS",
    "browserModel",
    "cardExpiryDate",
    "acctNumber",
    "deviceChannel",
    "mcc",
    "merchantCountryCode",
    "merchantName",
    "notificationURL",
    "purchaseAmount",
    "purchaseCurrency",
    "purchaseExponent",
    "purchaseDate",
    "transType",
    "acsOperatorID",
    "acsReferenceNumber",
    "dsReferenceNumber",
    "acsChallengeMandated",
    "authenticationType",
    "authenticationValue",
    "acsURL",
    "transStatus",
    "transStatusReason",
    "eci",
    "challengeWindowSize",
    "interactionCounter",
    "challengeCancel",
    "resultsStatus",
    "serialNum",
    "dsStartProtocolVersion",
    "dsEndProtocolVersion",
    "errorCode",
    "errorComponent",
    "errorDescription",
    "errorDetail",
    "errorMessageType",
    "rreqResultStatus",
    "rreqResultReason",
]

MESSAGE_SORT_ORDER = {
    "AReq": 10,
    "ARes": 20,
    "Erro": 25,
    "CReq": 30,
    "CRes": 40,
    "RReq": 50,
    "RReqResult": 52,
    "RRes": 60,
    "MethodExpired": 65,
    "PReq": 70,
    "PRes": 80,
}


@dataclass
class ThreeDsMessageRow:
    log_file: str
    message_datetime: str
    message_type: str
    message_direction: str = ""
    three_ds_server_trans_id: str = ""
    acs_trans_id: str = ""
    ds_trans_id: str = ""
    message_version: str = ""
    message_category: str = ""
    three_ds_comp_ind: str = ""
    three_ds_requestor_authentication_ind: str = ""
    three_ds_requestor_id: str = ""
    three_ds_requestor_name: str = ""
    three_ds_requestor_url: str = ""
    three_ds_server_ref_number: str = ""
    three_ds_server_operator_id: str = ""
    three_ds_server_url: str = ""
    acquirer_bin: str = ""
    acquirer_merchant_id: str = ""
    browser_accept_header: str = ""
    browser_java_enabled: str = ""
    browser_javascript_enabled: str = ""
    browser_language: str = ""
    browser_color_depth: str = ""
    browser_screen_height: str = ""
    browser_screen_width: str = ""
    browser_tz: str = ""
    browser_user_agent: str = ""
    card_expiry_date: str = ""
    acct_number: str = ""
    device_channel: str = ""
    mcc: str = ""
    merchant_country_code: str = ""
    merchant_name: str = ""
    notification_url: str = ""
    purchase_amount: str = ""
    purchase_currency: str = ""
    purchase_exponent: str = ""
    purchase_date: str = ""
    trans_type: str = ""
    acs_operator_id: str = ""
    acs_reference_number: str = ""
    ds_reference_number: str = ""
    acs_challenge_mandated: str = ""
    authentication_type: str = ""
    authentication_value: str = ""
    acs_url: str = ""
    trans_status: str = ""
    trans_status_reason: str = ""
    eci: str = ""
    challenge_window_size: str = ""
    interaction_counter: str = ""
    challenge_cancel: str = ""
    results_status: str = ""
    serial_num: str = ""
    ds_start_protocol_version: str = ""
    ds_end_protocol_version: str = ""
    error_code: str = ""
    error_component: str = ""
    error_description: str = ""
    error_detail: str = ""
    error_message_type: str = ""
    rreq_result_status: str = ""
    rreq_result_reason: str = ""
    source_index: int = 0

    def to_csv_dict(self) -> dict[str, str]:
        return {
            "logFile": self.log_file,
            "messageDateTime": self.message_datetime,
            "messageType": self.message_type,
            "messageDirection": self.message_direction,
            "threeDSServerTransID": self.three_ds_server_trans_id,
            "acsTransID": self.acs_trans_id,
            "dsTransID": self.ds_trans_id,
            "messageVersion": self.message_version,
            "messageCategory": self.message_category,
            "threeDSCompInd": self.three_ds_comp_ind,
            "threeDSRequestorAuthenticationInd": self.three_ds_requestor_authentication_ind,
            "threeDSRequestorID": self.three_ds_requestor_id,
            "threeDSRequestorName": self.three_ds_requestor_name,
            "threeDSRequestorURL": self.three_ds_requestor_url,
            "threeDSServerRefNumber": self.three_ds_server_ref_number,
            "threeDSServerOperatorID": self.three_ds_server_operator_id,
            "threeDSServerURL": self.three_ds_server_url,
            "acquirerBIN": self.acquirer_bin,
            "acquirerMerchantID": self.acquirer_merchant_id,
            "browserAcceptHeader": self.browser_accept_header,
            "browserJavaEnabled": self.browser_java_enabled,
            "browserJavascriptEnabled": self.browser_javascript_enabled,
            "browserLanguage": self.browser_language,
            "browserColorDepth": self.browser_color_depth,
            "browserScreenHeight": self.browser_screen_height,
            "browserScreenWidth": self.browser_screen_width,
            "browserTZ": self.browser_tz,
            "browserUserAgent": self.browser_user_agent,
            "cardExpiryDate": self.card_expiry_date,
            "acctNumber": self.acct_number,
            "deviceChannel": self.device_channel,
            "mcc": self.mcc,
            "merchantCountryCode": self.merchant_country_code,
            "merchantName": self.merchant_name,
            "notificationURL": self.notification_url,
            "purchaseAmount": self.purchase_amount,
            "purchaseCurrency": self.purchase_currency,
            "purchaseExponent": self.purchase_exponent,
            "purchaseDate": self.purchase_date,
            "transType": self.trans_type,
            "acsOperatorID": self.acs_operator_id,
            "acsReferenceNumber": self.acs_reference_number,
            "dsReferenceNumber": self.ds_reference_number,
            "acsChallengeMandated": self.acs_challenge_mandated,
            "authenticationType": self.authentication_type,
            "authenticationValue": self.authentication_value,
            "acsURL": self.acs_url,
            "transStatus": self.trans_status,
            "transStatusReason": self.trans_status_reason,
            "eci": self.eci,
            "challengeWindowSize": self.challenge_window_size,
            "interactionCounter": self.interaction_counter,
            "challengeCancel": self.challenge_cancel,
            "resultsStatus": self.results_status,
            "serialNum": self.serial_num,
            "dsStartProtocolVersion": self.ds_start_protocol_version,
            "dsEndProtocolVersion": self.ds_end_protocol_version,
            "errorCode": self.error_code,
            "errorComponent": self.error_component,
            "errorDescription": self.error_description,
            "errorDetail": self.error_detail,
            "errorMessageType": self.error_message_type,
            "rreqResultStatus": self.rreq_result_status,
            "rreqResultReason": self.rreq_result_reason,
        }


@dataclass
class ParseStats:
    total_rows: int = 0
    by_message_type: dict[str, int] = field(default_factory=dict)
