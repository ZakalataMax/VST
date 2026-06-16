WITH
areq AS (
    SELECT
        ds.messagedatetime,
        ds.threedsservertransid,
        ds.acctnumber,
        ds.merchantname,
        ds.browseruseragent
    FROM cust_acs_3dsmess ds
    WHERE ds.messagetype = 'AReq'
),
ares AS (
    SELECT
        ds.threedsservertransid,
        (array_agg(ds.transstatus ORDER BY ds.messagedatetime DESC))[1] AS transstatus,
        (array_agg(ds.transstatusreason ORDER BY ds.messagedatetime DESC))[1] AS transstatusreason
    FROM cust_acs_3dsmess ds
    WHERE ds.messagetype = 'ARes'
    GROUP BY ds.threedsservertransid
),
cres AS (
    SELECT
        ds.threedsservertransid,
        (array_agg(ds.transstatus ORDER BY ds.messagedatetime DESC))[1] AS transstatus,
        (array_agg(ds.transstatusreason ORDER BY ds.messagedatetime DESC))[1] AS transstatusreason
    FROM cust_acs_3dsmess ds
    WHERE ds.messagetype = 'CRes'
    GROUP BY ds.threedsservertransid
),
erro AS (
    SELECT
        ds.threedsservertransid,
        (array_agg(ds.errorcode ORDER BY ds.messagedatetime DESC))[1] AS errorcode
    FROM cust_acs_3dsmess ds
    WHERE ds.messagetype = 'Erro'
    GROUP BY ds.threedsservertransid
),
event_token AS (
    SELECT
        e.threedsservertransid,
        e.messagedatetime,
        CASE e.messagetype
            WHEN 'AReq' THEN 10
            WHEN 'ARes' THEN 20
            WHEN 'Erro' THEN 25
            WHEN 'CReq' THEN 30
            WHEN 'OobInitRequest' THEN 40
            WHEN 'OobInitResponse' THEN 50
            WHEN 'OobResultRequest' THEN 60
            WHEN 'OobResult' THEN 60
            WHEN 'OobResultResponse' THEN 70
            WHEN 'ChallengeAnswer' THEN 80
            WHEN 'ChallengeMethod' THEN 85
            WHEN 'AuthMethodSwitch' THEN 86
            WHEN 'ChallengeExpiring' THEN 90
            WHEN 'RReq' THEN 100
            WHEN 'RRes' THEN 110
            WHEN 'CRes' THEN 120
            WHEN 'ChallengeOutcome' THEN 130
            ELSE 50
        END AS tie_sort,
        CASE
            WHEN e.messagetype = 'AReq' THEN 'AReq'
            WHEN e.messagetype = 'ARes' THEN 'ARes(' || e.transstatus || ')'
            WHEN e.messagetype = 'CReq' THEN 'CReq'
            WHEN e.messagetype = 'OobInitRequest' THEN 'OobInitReq'
            WHEN e.messagetype = 'OobInitResponse' THEN 'OobInitResp'
            WHEN e.messagetype = 'OobResultRequest'
            THEN 'OobResultReq(' || e.oobresultstatus || '+' || e.oobresultmethod || ')'
            WHEN e.messagetype = 'OobResult' AND COALESCE(e.messagedirection, 'In') = 'In'
            THEN 'OobResultReq(' || e.oobresultstatus || '+' || e.oobresultmethod || ')'
            WHEN e.messagetype = 'OobResultResponse' THEN 'OobResultResp'
            WHEN e.messagetype = 'OobResult' AND e.messagedirection = 'Out' THEN 'OobResultResp'
            WHEN e.messagetype = 'ChallengeExpiring' THEN 'Challenge expired'
            WHEN e.messagetype = 'RReq'
            THEN 'RReq('
                || COALESCE(e.transstatus, 'NULL') || '+' || COALESCE(e.transstatusreason, 'NULL')
                || CASE
                     WHEN e.authenticationmethod IS NOT NULL
                     THEN ', AuthMethod=' || e.authenticationmethod
                     ELSE ''
                   END
                || CASE
                     WHEN e.challengecancel IS NOT NULL
                     THEN ', ChCancel=' || e.challengecancel
                     ELSE ''
                   END
                || ')'
            WHEN e.messagetype = 'RRes' THEN 'RRes'
            WHEN e.messagetype = 'CRes' THEN 'CRes(' || COALESCE(e.transstatus, '') || ')'
            WHEN e.messagetype = 'ChallengeAnswer'
            THEN 'ChAnswerRequest(submit=' || e.challengesubmit || ')'
            WHEN e.messagetype = 'Erro' AND e.errorcode IS NOT NULL
            THEN 'Erro(' || e.errorcode || ')'
            WHEN e.messagetype = 'ChallengeMethod'
            THEN 'ChMethod('
                || CASE
                     WHEN e.challengemethod LIKE 'OTP%%' THEN 'OTP'
                     WHEN e.challengemethod LIKE 'OOB%%' THEN 'OOB'
                     ELSE e.challengemethod
                   END
                || '+' || e.challengemethodcode || ')'
            WHEN e.messagetype = 'ChallengeOutcome' AND LOWER(e.ischallengesucceeded) = 'true'
            THEN 'IsChallengeSucceded: true'
            WHEN e.messagetype = 'ChallengeOutcome' AND LOWER(e.ischallengesucceeded) = 'false'
            THEN 'IsChallengeSucceded: false'
            WHEN e.messagetype = 'AuthMethodSwitch'
            THEN 'OOB to OTP: ' || REPLACE(e.authmethodswitch, '->', ' -> ')
        END AS token
    FROM cust_acs_3dsmess e
    WHERE e.threedsservertransid IS NOT NULL
),
timeline AS (
    SELECT
        et.threedsservertransid,
        string_agg(et.token, ' ' ORDER BY et.messagedatetime, et.tie_sort) AS txn_timeline
    FROM event_token et
    WHERE et.token IS NOT NULL
    GROUP BY et.threedsservertransid
),
acs_id AS (
    SELECT
        ds.threedsservertransid,
        max(ds.acstransid) AS acs_trans_id
    FROM cust_acs_3dsmess ds
    WHERE coalesce(ds.acstransid, '') != ''
    GROUP BY ds.threedsservertransid
),
oob_init AS (
    SELECT
        ds.threedsservertransid,
        count(*) FILTER (WHERE ds.messagetype = 'OobInitRequest') AS oob_init_req_count,
        count(*) FILTER (WHERE ds.messagetype = 'OobInitResponse') AS oob_init_resp_count
    FROM cust_acs_3dsmess ds
    WHERE ds.messagetype IN ('OobInitRequest', 'OobInitResponse')
      AND ds.threedsservertransid IS NOT NULL
    GROUP BY ds.threedsservertransid
)
SELECT
    substr(areq.messagedatetime, 9, 2) || '.' || substr(areq.messagedatetime, 6, 2) || '.' || substr(areq.messagedatetime, 1, 4) AS areq_messagedate,
    'CRES: ' || COALESCE(cres.transstatus, 'NULL')
        || '+' || COALESCE(cres.transstatusreason, 'NULL') AS final_cres_status,
    timeline.txn_timeline,
    areq.browseruseragent AS browser_user_agent,
    areq.merchantname AS merchant_name,
    areq.threedsservertransid,
    acs_id.acs_trans_id,
    areq.messagedatetime AS areq_messagedatetime,
    CASE
        WHEN areq.acctnumber LIKE '4%%' THEN 'Visa'
        WHEN areq.acctnumber LIKE '5%%' THEN 'MC'
    END AS card_scheme,
    'ARES: ' || COALESCE(ares.transstatus, 'NULL')
        || '+' || COALESCE(ares.transstatusreason, 'NULL') AS ares_status,
    CASE
        WHEN timeline.txn_timeline LIKE '%%Erro(%%' THEN 'Erro'
        WHEN timeline.txn_timeline LIKE '%%Challenge expired%%' THEN 'Timeout'
        WHEN timeline.txn_timeline LIKE '%%OOB to OTP%%' THEN 'OOB_to_OTP'
        WHEN timeline.txn_timeline LIKE '%%IsChallengeSucceded: false%%' THEN 'Challenge_FAIL'
        WHEN timeline.txn_timeline LIKE '%%IsChallengeSucceded: true%%' THEN 'Challenge_OK'
        WHEN timeline.txn_timeline LIKE '%%OobResultReq%%' THEN 'OOB_flow'
        WHEN timeline.txn_timeline LIKE '%%OobInitReq%%' THEN 'OOB_started'
        ELSE 'Other'
    END AS txn_result,
    COALESCE(oob_init.oob_init_req_count, 0) AS oob_init_req_count,
    COALESCE(oob_init.oob_init_resp_count, 0) AS oob_init_resp_count,
    greatest(
        COALESCE(oob_init.oob_init_req_count, 0) - COALESCE(oob_init.oob_init_resp_count, 0),
        0
    ) AS oob_init_missing_resp_count,
    erro.errorcode,
    areq.acctnumber AS acct_number
FROM areq
LEFT JOIN ares ON areq.threedsservertransid = ares.threedsservertransid
LEFT JOIN cres ON areq.threedsservertransid = cres.threedsservertransid
LEFT JOIN timeline ON areq.threedsservertransid = timeline.threedsservertransid
LEFT JOIN erro ON areq.threedsservertransid = erro.threedsservertransid
LEFT JOIN acs_id ON areq.threedsservertransid = acs_id.threedsservertransid
LEFT JOIN oob_init ON areq.threedsservertransid = oob_init.threedsservertransid
WHERE (%(txn_id)s::text IS NULL OR areq.threedsservertransid = %(txn_id)s::text)
  AND areq.messagedatetime >= %(date_from)s::text
  AND (%(date_to)s::text IS NULL OR areq.messagedatetime <= %(date_to)s::text)
ORDER BY 1
