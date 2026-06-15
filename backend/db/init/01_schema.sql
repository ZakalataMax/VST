CREATE TABLE IF NOT EXISTS cust_acs_3dsmess (
    messagedatetime TEXT,
    messagetype TEXT,
    messagedirection TEXT,
    threedsservertransid TEXT,
    acstransid TEXT,
    transtype TEXT,
    transstatus TEXT,
    transstatusreason TEXT,
    interactioncounter TEXT,
    authenticationmethod TEXT,
    authenticationtype TEXT,
    eci TEXT,
    resultsstatus TEXT,
    acscounteratos TEXT,
    challengecompletionind TEXT,
    challengecancel TEXT,
    threedsserveroperatorid TEXT,
    acquirermerchantid TEXT,
    acctnumber TEXT,
    acquirerbin TEXT,
    browserip TEXT,
    browseruseragent TEXT,
    errorcode TEXT,
    ischallengeexpired TEXT,
    oobresultstatus TEXT,
    oobresultmethod TEXT,
    challengemethod TEXT,
    challengemethodcode TEXT,
    ischallengesucceeded TEXT,
    challengesubmit TEXT,
    authmethodswitch TEXT,
    creqincoming TEXT
);

CREATE INDEX IF NOT EXISTS idx_cust_acs_3dsmess_messagetype ON cust_acs_3dsmess (messagetype);
CREATE INDEX IF NOT EXISTS idx_cust_acs_3dsmess_threedsservertransid ON cust_acs_3dsmess (threedsservertransid);
CREATE INDEX IF NOT EXISTS idx_cust_acs_3dsmess_messagedatetime ON cust_acs_3dsmess (messagedatetime);

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'vst_readonly') THEN
        CREATE ROLE vst_readonly WITH LOGIN PASSWORD 'vst_readonly';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE vst TO vst_readonly;
GRANT USAGE ON SCHEMA public TO vst_readonly;
GRANT SELECT ON cust_acs_3dsmess TO vst_readonly;
