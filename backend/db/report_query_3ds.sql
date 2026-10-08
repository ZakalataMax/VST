WITH
report_areq AS (
    SELECT
        ds.messagedatetime,
        ds.threedsservertransid,
        ds.acctnumber,
        ds.merchantname,
        ds.browseruseragent,
        ds.browseros,
        ds.browsermodel,
        ds.threedsrequestorurl,
        ds.threedsserverurl,
        ds.threedsrequestorname,
        ds.purchaseamount,
        ds.purchasecurrency,
        ds.purchasedate
    FROM cust_3ds_server_mess ds
    WHERE ds.messagetype = 'AReq'
      AND (%(txn_id)s::text IS NULL OR ds.threedsservertransid = %(txn_id)s::text)
      AND ds.messagedatetime >= %(date_from)s::text
      AND (%(date_to)s::text IS NULL OR ds.messagedatetime <= %(date_to)s::text)
),
report_txn AS (
    SELECT DISTINCT threedsservertransid
    FROM report_areq
),
areq AS (
    SELECT * FROM report_areq
),
ares AS (
    SELECT
        ds.threedsservertransid,
        (array_agg(ds.transstatus ORDER BY ds.messagedatetime DESC))[1] AS transstatus,
        (array_agg(ds.transstatusreason ORDER BY ds.messagedatetime DESC))[1] AS transstatusreason
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
    WHERE ds.messagetype = 'ARes'
    GROUP BY ds.threedsservertransid
),
cres AS (
    SELECT
        ds.threedsservertransid,
        (array_agg(ds.transstatus ORDER BY ds.messagedatetime DESC))[1] AS transstatus
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
    WHERE ds.messagetype = 'CRes'
    GROUP BY ds.threedsservertransid
),
rreq AS (
    SELECT
        ds.threedsservertransid,
        (array_agg(ds.transstatus ORDER BY ds.messagedatetime DESC))[1] AS transstatus,
        (array_agg(ds.transstatusreason ORDER BY ds.messagedatetime DESC))[1] AS transstatusreason
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
    WHERE ds.messagetype = 'RReq'
    GROUP BY ds.threedsservertransid
),
rreq_result AS (
    SELECT
        ds.threedsservertransid,
        (array_agg(ds.rreqresultstatus ORDER BY ds.messagedatetime DESC))[1] AS rreqresultstatus,
        (array_agg(ds.rreqresultreason ORDER BY ds.messagedatetime DESC))[1] AS rreqresultreason
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
    WHERE ds.messagetype = 'RReqResult'
    GROUP BY ds.threedsservertransid
),
method_expired AS (
    SELECT DISTINCT ds.threedsservertransid
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
    WHERE ds.messagetype = 'MethodExpired'
),
erro AS (
    SELECT
        ds.threedsservertransid,
        (array_agg(ds.errorcode ORDER BY ds.messagedatetime DESC))[1] AS errorcode,
        (array_agg(ds.errordescription ORDER BY ds.messagedatetime DESC))[1] AS errordescription
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
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
            WHEN 'CRes' THEN 40
            WHEN 'RReq' THEN 50
            WHEN 'RReqResult' THEN 52
            WHEN 'RRes' THEN 60
            WHEN 'MethodExpired' THEN 65
            WHEN 'PReq' THEN 70
            WHEN 'PRes' THEN 80
            ELSE 50
        END AS tie_sort,
        CASE
            WHEN e.messagetype = 'AReq' THEN 'AReq'
            WHEN e.messagetype = 'ARes'
            THEN 'ARes(' || COALESCE(e.transstatus, 'NULL') || '+' || COALESCE(e.transstatusreason, 'NULL') || ')'
            WHEN e.messagetype = 'CReq' THEN 'CReq'
            WHEN e.messagetype = 'CRes' THEN 'CRes(' || COALESCE(e.transstatus, 'NULL') || ')'
            WHEN e.messagetype = 'RReq'
            THEN 'RReq(' || COALESCE(e.transstatus, 'NULL') || '+' || COALESCE(e.transstatusreason, 'NULL') || ')'
            WHEN e.messagetype = 'RReqResult'
            THEN 'Result(' || COALESCE(e.rreqresultstatus, 'NULL') || '/' || COALESCE(e.rreqresultreason, 'NULL') || ')'
            WHEN e.messagetype = 'RRes' THEN 'RRes'
            WHEN e.messagetype = 'MethodExpired' THEN '3DSMethodExpired'
            WHEN e.messagetype = 'PReq' THEN 'PReq'
            WHEN e.messagetype = 'PRes' THEN 'PRes'
            WHEN e.messagetype = 'Erro' AND e.errorcode IS NOT NULL
            THEN 'Erro(' || e.errorcode || ')'
        END AS token
    FROM cust_3ds_server_mess e
    INNER JOIN report_txn t ON e.threedsservertransid = t.threedsservertransid
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
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
    WHERE coalesce(ds.acstransid, '') != ''
    GROUP BY ds.threedsservertransid
),
success_ares AS (
    SELECT DISTINCT ds.threedsservertransid
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
    WHERE ds.messagetype = 'ARes' AND COALESCE(ds.transstatus, '') = 'Y'
),
success_rreq AS (
    SELECT DISTINCT ds.threedsservertransid
    FROM cust_3ds_server_mess ds
    INNER JOIN report_txn t ON ds.threedsservertransid = t.threedsservertransid
    WHERE ds.messagetype = 'RReq' AND COALESCE(ds.transstatus, '') = 'Y'
)
SELECT
    CASE
        WHEN success_ares.threedsservertransid IS NOT NULL
          OR success_rreq.threedsservertransid IS NOT NULL
        THEN 'YES'
        ELSE 'NO'
    END AS general_success,
    vst_st_louis_date(areq.messagedatetime) AS areq_messagedate_stlouis,
    substr(areq.messagedatetime, 9, 2) || '.' || substr(areq.messagedatetime, 6, 2) || '.' || substr(areq.messagedatetime, 1, 4) AS areq_messagedate,
    COALESCE(areq.browseros, '') AS browser_os,
    COALESCE(areq.browsermodel, '') AS browser_model,
    timeline.txn_timeline,
    areq.browseruseragent AS browser_user_agent,
    areq.merchantname AS merchant_name,
    'URL: ' || COALESCE(areq.threedsrequestorurl, 'NULL')
        || ' | Server: ' || COALESCE(areq.threedsserverurl, 'NULL')
        || ' | Requestor: ' || COALESCE(areq.threedsrequestorname, 'NULL') AS three_ds_requestor_info,
    areq.threedsservertransid,
    acs_id.acs_trans_id,
    areq.messagedatetime AS areq_messagedatetime,
    CASE
        WHEN areq.acctnumber LIKE '4%%' THEN 'Visa'
        WHEN areq.acctnumber LIKE '5%%' THEN 'MC'
    END AS card_scheme,
    'ARES: ' || COALESCE(ares.transstatus, 'NULL')
        || '+' || COALESCE(ares.transstatusreason, 'NULL') AS ares_status,
    'CRES: ' || COALESCE(cres.transstatus, 'NULL') AS final_cres_status,
    'RREQ: ' || COALESCE(rreq.transstatus, 'NULL')
        || '+' || COALESCE(rreq.transstatusreason, 'NULL') AS rreq_status,
    CASE
        WHEN rreq_result.rreqresultstatus IS NOT NULL
        THEN rreq_result.rreqresultstatus || ' / ' || COALESCE(rreq_result.rreqresultreason, 'null')
        ELSE NULL
    END AS rreq_result_description,
    CASE WHEN method_expired.threedsservertransid IS NOT NULL THEN 'YES' ELSE NULL END AS method_expired,
    erro.errorcode,
    erro.errordescription,
    areq.acctnumber AS acct_number,
    areq.purchaseamount AS purchase_amount,
    areq.purchasecurrency AS purchase_currency,
    areq.purchasedate AS purchase_date,
    CASE
        WHEN erro.threedsservertransid IS NOT NULL THEN 'Erro'
        WHEN rreq.transstatus = 'Y' THEN 'SUCCESS'
        WHEN rreq.transstatus = 'N' THEN 'DENIED'
        WHEN rreq.transstatus = 'R' THEN 'REJECTED'
        WHEN rreq.transstatus = 'U' THEN 'UNABLE'
        WHEN rreq.threedsservertransid IS NOT NULL THEN 'Other'
        WHEN ares.transstatus = 'N' THEN 'DECLINED_NO_CHALLENGE'
        WHEN ares.transstatus = 'C' THEN 'CHALLENGE_NO_RESULT'
        ELSE 'Other'
    END AS txn_result
FROM areq
LEFT JOIN ares ON areq.threedsservertransid = ares.threedsservertransid
LEFT JOIN cres ON areq.threedsservertransid = cres.threedsservertransid
LEFT JOIN rreq ON areq.threedsservertransid = rreq.threedsservertransid
LEFT JOIN rreq_result ON areq.threedsservertransid = rreq_result.threedsservertransid
LEFT JOIN method_expired ON areq.threedsservertransid = method_expired.threedsservertransid
LEFT JOIN timeline ON areq.threedsservertransid = timeline.threedsservertransid
LEFT JOIN erro ON areq.threedsservertransid = erro.threedsservertransid
LEFT JOIN acs_id ON areq.threedsservertransid = acs_id.threedsservertransid
LEFT JOIN success_ares ON areq.threedsservertransid = success_ares.threedsservertransid
LEFT JOIN success_rreq ON areq.threedsservertransid = success_rreq.threedsservertransid
ORDER BY areq.messagedatetime
