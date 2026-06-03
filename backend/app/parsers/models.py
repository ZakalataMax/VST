from __future__ import annotations

from dataclasses import dataclass, field

CSV_COLUMNS = [
    "logFile",
    "messageDateTime",
    "messageType",
    "messageDirection",
    "threeDSServerTransID",
    "transType",
    "transStatus",
    "transStatusReason",
    "interactionCounter",
    "authenticationMethod",
    "authenticationType",
    "eci",
    "resultsStatus",
    "acsCounterAtoS",
    "challengeCompletionInd",
    "challengeCancel",
    "threeDSServerOperatorID",
    "acquirerMerchantID",
    "merchantName",
    "acctNumber",
    "acquirerBIN",
    "browserIP",
    "errorCode",
    "isChallengeExpired",
    "oobResultStatus",
    "oobResultMethod",
    "challengeMethod",
    "challengeMethodCode",
    "isChallengeSucceeded",
    "challengeSubmit",
    "authMethodSwitch",
    "creqIncoming",
]

MESSAGE_SORT_ORDER = {
    "AReq": 10,
    "ARes": 20,
    "Erro": 25,
    "CReq": 30,
    "OobInitRequest": 40,
    "OobInitResponse": 50,
    "OobResultResponse": 60,
    "OobResultRequest": 61,
    "AuthMethodSwitch": 65,
    "ChallengeMethod": 70,
    "ChallengeAnswer": 71,
    "ChallengeOutcome": 72,
    "ChallengeExpiring": 90,
    "RReq": 100,
    "RRes": 110,
    "CRes": 120,
}


@dataclass
class MessageRow:
    log_file: str
    message_datetime: str
    message_type: str
    message_direction: str = ""
    three_ds_server_trans_id: str = ""
    trans_type: str = ""
    trans_status: str = ""
    trans_status_reason: str = ""
    interaction_counter: str = ""
    authentication_method: str = ""
    authentication_type: str = ""
    eci: str = ""
    results_status: str = ""
    acs_counter_atos: str = ""
    challenge_completion_ind: str = ""
    challenge_cancel: str = ""
    three_ds_server_operator_id: str = ""
    acquirer_merchant_id: str = ""
    merchant_name: str = ""
    acct_number: str = ""
    acquirer_bin: str = ""
    browser_ip: str = ""
    error_code: str = ""
    is_challenge_expired: str = ""
    oob_result_status: str = ""
    oob_result_method: str = ""
    challenge_method: str = ""
    challenge_method_code: str = ""
    is_challenge_succeeded: str = ""
    challenge_submit: str = ""
    auth_method_switch: str = ""
    creq_incoming: str = ""
    source_index: int = 0

    def to_csv_dict(self) -> dict[str, str]:
        return {
            "logFile": self.log_file,
            "messageDateTime": self.message_datetime,
            "messageType": self.message_type,
            "messageDirection": self.message_direction,
            "threeDSServerTransID": self.three_ds_server_trans_id,
            "transType": self.trans_type,
            "transStatus": self.trans_status,
            "transStatusReason": self.trans_status_reason,
            "interactionCounter": self.interaction_counter,
            "authenticationMethod": self.authentication_method,
            "authenticationType": self.authentication_type,
            "eci": self.eci,
            "resultsStatus": self.results_status,
            "acsCounterAtoS": self.acs_counter_atos,
            "challengeCompletionInd": self.challenge_completion_ind,
            "challengeCancel": self.challenge_cancel,
            "threeDSServerOperatorID": self.three_ds_server_operator_id,
            "acquirerMerchantID": self.acquirer_merchant_id,
            "merchantName": self.merchant_name,
            "acctNumber": self.acct_number,
            "acquirerBIN": self.acquirer_bin,
            "browserIP": self.browser_ip,
            "errorCode": self.error_code,
            "isChallengeExpired": self.is_challenge_expired,
            "oobResultStatus": self.oob_result_status,
            "oobResultMethod": self.oob_result_method,
            "challengeMethod": self.challenge_method,
            "challengeMethodCode": self.challenge_method_code,
            "isChallengeSucceeded": self.is_challenge_succeeded,
            "challengeSubmit": self.challenge_submit,
            "authMethodSwitch": self.auth_method_switch,
            "creqIncoming": self.creq_incoming,
        }


@dataclass
class ParseStats:
    total_rows: int = 0
    by_message_type: dict[str, int] = field(default_factory=dict)
