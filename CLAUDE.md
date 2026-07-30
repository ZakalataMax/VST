# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

VST Work Tools — a PySide6 desktop app that downloads ACS (3-D Secure Access Control Server) logs from Elastic, parses them into daily CSVs, and builds DuckDB-powered Excel pivot reports. Everything lives under `backend/`; there is no frontend/, server, or API — it's a single-machine desktop tool. Distributed as a PyInstaller onefile exe (`VST.exe`) with no Python install required on the target machine.

## Commands

All commands run from `backend/`.

```bash
pip install -r requirements.txt
cp .env.example .env                  # fill in ELASTIC_PASS (required) before running
python -m desktop                     # run the app in dev mode (uses backend/data/)
python -m unittest discover -s tests -p "test_*.py" -v   # run all tests
python -m unittest tests.test_auth_method_switch_ids -v  # run a single test module
build.bat                             # (or build.sh) installs deps + pyinstaller, builds dist/VST.exe via vst.spec
```

`pyrightconfig.json` at the repo root type-checks `backend/app` and `backend/desktop`.

Git hooks: run `setup-hooks.sh` (or `.bat`) once to point `core.hooksPath` at `.githooks`. The `pre-push` hook runs the same `unittest discover` command before every push — keep it green.

## Configuration (`.env`)

`app/config.py`'s `load_env_file()` reads `.env` (next to `VST.exe` when frozen, `backend/.env` in dev) at startup and sets any var **not already present** in the environment — existing env vars always win. See `.env.example` for the full list; `ELASTIC_PASS` is the only required one. `build.bat`/`build.sh` copy `backend/.env` to `dist/.env` after every build. Other notable vars: `ELASTIC_USER`/`ELASTIC_URL`/`ELASTIC_INDEX`/`ELASTIC_HOSTS`/`ELASTIC_TIME_ZONE` (query shape), `ELASTIC_VERIFY_TLS`/`ELASTIC_CA_BUNDLE` (TLS, off by default — internal endpoint uses a self-signed cert), `ELASTIC_MAX_DROPPED`/`PARSER_MAX_DROPPED` (data-integrity thresholds, see below), `LOG_STORAGE_DIR`/`CSV_STORAGE_DIR`/`REPORT_OUTPUT_DIR` (path overrides), `REPORT_EMAIL_TO`/`REPORT_EMAIL_SUBJECT` (recipient(s)/subject for report emails sent via Outlook COM automation — used by both the daily automation job and the desktop app's "Email report" export option; `app/services/report_mailer.py` is the single file with recipients/subject/default body-text/send logic for these emails).

## Architecture

### Two layers: `app/` (headless logic) and `desktop/` (PySide6 UI)

`desktop/` never touches parsing/storage internals directly except through `app.parsers` / `app.services` functions — the UI is a thin driver over the backend logic and long-running work runs in `desktop/workers.py` QThread workers so the UI stays responsive.

- `desktop/tabs/parser_tab.py` — standalone number-list formatting/dedup utility (SQL-quoted or plain), unrelated to ACS parsing.
- `desktop/tabs/logs_tab.py` — the main workflow: **Import & Parse** downloads a date range from Elastic and parses it into daily CSV, **Report** picks a range and runs/exports the pivot report. Backed by `widgets/import_parse_panel.py`, `widgets/coverage_sidebar.py` (+ `desktop/coverage_utils.py` for per-day status/action derivation), `widgets/report_panel.py`.
- `desktop/report_sql_utils.py` — rewrites literal `areq.messagedatetime >= 'YYYY-MM-DD'` filters in the custom-SQL editor when the UI date pickers change.
- `desktop/__main__.py` loads `.env` and installs a crash hook that appends uncaught exceptions to `vst-error.log` next to the exe/`.env`, before importing `desktop.main_window` (import errors get logged too).

### Log acquisition (`app/services/elastic_logs.py`, `app/services/log_storage.py`)

Logs are downloaded from Elastic via a SQL-over-HTTP proxy endpoint (`_sql?format=csv`), not uploaded manually — there is no file-upload UI anymore. `download_day()` fetches a calendar day in 30-minute chunks (basic auth via `ELASTIC_USER`/`ELASTIC_PASS`), recursively bisecting a chunk down to 1-minute windows on a retryable HTTP error or when a chunk returns the `QUERY_LIMIT` row cap (to avoid silent truncation — if even the 1-minute window hits the cap, the whole download fails loudly instead of saving partial data). Rows with unparseable timestamps are dropped and counted; if `dropped_count` exceeds `ELASTIC_MAX_DROPPED` the day aborts instead of saving. Results are stored as `data/logs/{date}/elastic.log` (+ `elastic.meta.json` with `partial`/`rowCount`/min/max datetime) via `save_elastic_log`. `should_skip_download`/`plan_download_dates` skip re-downloading a day only if it was already downloaded **and** is fully complete (not "today", not partial) — the current/partial day is always refreshed.

`log_storage.py` still understands the legacy `acs1`/`acs2` upload format (`save_upload`, paired-file validation) purely for backward compatibility with previously-uploaded data on disk — `read_day_for_parse` prefers `elastic.log` for a day when present, falling back to the `acs1`+`acs2` pair otherwise.

### Parsing pipeline (`app/parsers/acs_log_parser.py`)

Log lines are plain text with either a `Key=value` style message (regex-matched in `patterns.py`) or a JSON payload wrapped in `Incoming message: [...]` / `Outgoing message: [...]`. `parse_log_content` / `parse_log_files` is the entry point:

1. A line is only routed to JSON-payload parsing if it literally contains the substring `"Incoming message:"` or `"Outgoing message:"` (`_parse_incoming_line` / `_parse_outgoing_line`); everything else falls through to the plain-text regexes (challenge method/answer/succeeded/expiring/auth-switch) in `patterns.py`.
2. For JSON payloads, `field_mapping.py`'s `JSON_FIELD_MAP` copies fields onto a `MessageRow` (`models.py`) by exact JSON-key → snake_case-attr mapping.
3. Rows get a `source_index` (`file_index * 10_000_000 + line_no`) so multi-file merges sort deterministically by `(message_datetime, MESSAGE_SORT_ORDER[message_type], source_index)` — `MESSAGE_SORT_ORDER` in `models.py` defines canonical event ordering within the same timestamp (AReq → ARes → CReq → Oob* → AuthMethodSwitch → Challenge* → RReq/RRes → CRes).
4. Malformed JSON is never silently swallowed: pass a `ParseDiagnostics()` instance through and it records a drop reason per bad payload. Callers (`desktop/workers.py`'s `ParseLogsWorker`, `app/jobs/daily_report.py`) compare `diagnostics.dropped_count` against `max_dropped_lines()` (`PARSER_MAX_DROPPED` env var, default 100) and refuse to save the day's CSV if the threshold is exceeded — same "fail loud instead of dropping data quietly" philosophy as the Elastic downloader.

**Known quirk (see `patterns.py` comment and `tests/test_auth_method_switch_ids.py`):** the ACS log swaps the `acsTxnId`/`tdssTxnId` labels specifically in the "Switch auth method" line — `acsTxnId` there actually holds the 3DS Server transaction ID and vice versa. Every other challenge-related line (`Challenge is expiring/succeeded/not accepted`) uses the labels normally. `AUTH_METHOD_SWITCH_RE`'s group mapping intentionally differs from the others — don't "fix" it to match.

### Storage (`app/services/csv_storage.py`, `app/parsers/csv_writer.py`)

- Parsed rows are written one CSV-per-day (`data/csv/{date}.csv`, `;`-delimited), plus a `.meta.json` sidecar (row count, min/max datetime, whether the day has full 00:00–24:00 coverage). `CSV_TO_DB` in `csv_storage.py` is the canonical camelCase-CSV-column → lowercase-DB-column mapping used everywhere reports run.
- `csv_writer.py` enriches every row at write time: if `browserUserAgent` is set, `app/services/device_detection.py`'s `parse_browser_device()` derives `browserOS`/`browserModel` (regex device/OS sniffing, with an Android raw-model → marketing-name lookup backed by the bundled `app/data/android_model_aliases.json` — regenerate that file with `scripts/generate_android_model_aliases.py`, a dev-only script, not run at runtime). Both columns are added to `CSV_COLUMNS` (`models.py`) and `CSV_TO_DB`.
- `resolve_csv_paths_for_dates` now **hard-fails** if any day in a requested range has no parsed CSV ("Report range has unparsed day(s)...") — a report range is all-or-nothing, unlike the old behavior of silently loading whatever existed.
- `db/init/*.sql` is a **legacy Postgres schema, not used by any code path** — the app never connects to Postgres; DuckDB reads the CSVs directly.

### Report engine (`app/services/file_report.py`, `app/services/report.py`, `db/report_query.sql`)

CSVs for the requested date range (or all of them) are loaded into an in-memory DuckDB **table** `cust_acs_3dsmess` (a table, not a view, so browser columns can be backfilled via `ALTER TABLE`/`UPDATE` for old CSVs that predate `browserOS`/`browserModel` — see `_enrich_browser_device_columns`, which registers `vst_browser_os`/`vst_browser_model` DuckDB UDFs backed by `device_detection.py`). Either the template query (`db/report_query.sql`, one row per `AReq` transaction with the timeline of every subsequent message rendered as one string) or a user-supplied custom SQL then runs against it.

- `%(date_from)s` / `%(date_to)s` / `%(txn_id)s` psycopg-style placeholders are rewritten to DuckDB `?` params by `_adapt_report_sql_for_duckdb` — the template SQL is authored once and shared between "date mode", "txn ID mode", and as the default loaded into the custom-SQL editor.
- `db/report_query.sql` filters `AReq` rows by the bound params *first* (`report_areq`/`report_txn` CTEs), then every other CTE `INNER JOIN`s against `report_txn` — this keeps the query from scanning the full multi-day table once a narrow date/txn filter is applied. It also computes `r02` (whether any `ARes` had `transstatus='R'`/`transstatusreason='02'`) and exposes `browser_os`/`browser_model`.
- A module-level cache (`_materialized_report`/`_cache`, cleared via `clear_report_cache()`) keeps one open DuckDB connection keyed by a CSV-file signature (path+mtime+size) plus the report SQL+params, so paginating through `run_report_query` or re-running with the same CSVs doesn't reload/re-enrich the whole table every call.
- `export_report_xlsx` writes a `Data` sheet (via DuckDB's `COPY ... FORMAT xlsx` when the `excel` extension loads, else an `openpyxl` write-only fallback), a computed `Summary` sheet (`txn_result` counts + percentages), and, when `native_pivot=True`, a `Pivot` sheet from `app/services/excel_pivot.py`: a fully-built native pivot table via Excel COM automation (`pywin32`, only works if Excel is installed and row count ≤ `NATIVE_PIVOT_MAX_ROWS`) or, as a fallback, a refresh-on-open pivot cache embedded with `openpyxl.pivot.*` that populates itself the next time the file is opened in Excel.

### Automation (`app/jobs/daily_report.py`)

A CLI entry point (`python -m app.jobs.daily_report`) that runs the same rolling-window flow as the desktop app unattended: download + parse the last `DEFAULT_WINDOW_DAYS` (10) days via the same `elastic_logs`/`log_storage`/`csv_storage` functions, export the report, and email it via `app/services/report_mailer.py` (Outlook COM automation only, through `app/services/outlook_sender.py` — the job silently skips emailing if `REPORT_EMAIL_TO` isn't set, or reports "Outlook automation unavailable" if `pywin32`/Outlook aren't available). Writes a `run-summary-*.json` next to the reports on every run. Not yet wired to a scheduler (no cron/Task Scheduler entry in this repo) — that wiring is external to this codebase.

### Config / paths

`app/paths.py` resolves storage dirs relative to the exe/script location (`sys.frozen` check for PyInstaller), overridable via `LOG_STORAGE_DIR` / `CSV_STORAGE_DIR` / `REPORT_OUTPUT_DIR` env vars (see Configuration above). `backend/data/`, `backend/build/`, `backend/dist/` are all gitignored — never treat their contents as source.

### Packaging

`vst.spec` lists every `desktop.*`/`app.*` submodule explicitly in `hiddenimports` (PyInstaller can't always discover them via static analysis) — new modules under `desktop/` or `app/` must be added there or they'll be missing from `VST.exe`. Bundled data files: `db/report_query.sql` and `app/data/android_model_aliases.json`, both loaded at runtime relative to `app/paths.py`'s `get_bundle_dir()`. `win32com`/`pythoncom`/`pywintypes` (from `pywin32`, Windows-only per `requirements.txt`) are hidden-imported for the native-pivot COM automation path; the app must still work without Excel installed (`native_pivot_available()` gates it).

## Workflow note (from README)

Dev machine (Cursor) edits/commits `backend/` source; VDI only pulls and runs `build.bat` (or `pull-build.bat`) to rebuild `VST.exe`. `backend/dist/data/` on VDI holds real user data and must never be pushed to git.
