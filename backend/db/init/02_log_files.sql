CREATE TABLE IF NOT EXISTS log_file (
    id            SERIAL PRIMARY KEY,
    log_date      DATE NOT NULL,
    acs_node      TEXT NOT NULL CHECK (acs_node IN ('acs1', 'acs2')),
    filename      TEXT NOT NULL,
    file_size     BIGINT NOT NULL,
    storage_path  TEXT NOT NULL,
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (log_date, acs_node)
);

CREATE INDEX IF NOT EXISTS idx_log_file_log_date ON log_file (log_date);

GRANT SELECT ON log_file TO vst_readonly;
