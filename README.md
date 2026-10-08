# VST Work Tools

Desktop app (PySide6) with three tools: **ACS Log Parser** (downloads ACS logs from
Elastic, parses them into daily CSV tables, builds DuckDB pivot reports, exports to
Excel), **3DS Log Parser** (same download/parse/report flow for 3DS Server logs), and
**Parser** (a standalone number formatting/dedup utility).

## Workflow: dev machine -> VDI

**Dev (Cursor):** edit source under `backend/`, commit and push. Do not commit `build/`,
`dist/`, or `data/`.

**VDI:** pull and build only:

```bat
pull-build.bat
```

Or manually:

```bat
git pull
cd backend
build.bat
```

Create a desktop shortcut to `backend\dist\VST.exe`. User data stays in
`backend\dist\data\` on VDI and is never pushed to git.

## Configuration (.env)

Copy `backend/.env.example` to `.env` and fill in the values. On VDI the build copies
`backend\.env` to `dist\.env` next to `VST.exe`. Existing environment variables are never
overwritten by the file.

Required:

- `ELASTIC_PASS` — Elastic password used to download logs.

Common optional settings: `ELASTIC_USER`, `ELASTIC_URL`, `ELASTIC_INDEX`,
`ELASTIC_HOSTS`, `ELASTIC_3DS_APP_NAME`, `ELASTIC_3DS_HOSTS`, `ELASTIC_VERIFY_TLS`,
`ELASTIC_CA_BUNDLE`, `LOG_STORAGE_DIR`, `CSV_STORAGE_DIR`, `REPORT_OUTPUT_DIR`,
`THREEDS_LOG_STORAGE_DIR`, `THREEDS_CSV_STORAGE_DIR`, `THREEDS_REPORT_OUTPUT_DIR`.
See `.env.example` for the full list.

Storing `.env` next to the exe on a trusted single-user VDI is an intentional choice for
this internal tool.

## Daily use (VDI)

1. Run `VST.exe` from the shortcut. The app opens on the **ACS Log Parser** tab.
2. **Import & Parse:** pick a date range and download logs from Elastic. Downloaded days
   are parsed automatically. Re-downloading a day refreshes its parsed CSV automatically.
3. **Report:** selecting days fills the report From/To range. **Run** builds the pivot
   preview; **Export** writes a timestamped `.xlsx` file with a `Data` sheet, a computed
   `Summary` sheet (`txn_result` count + %), and, when Microsoft Excel is installed, a
   fully built native `Pivot` sheet (transaction tree with count and % of total) you can
   reconfigure.
4. Send the exported report by email (manual today; see the automation note below).

Data layout next to the exe:

- `data/logs/{date}/elastic.log` — raw logs downloaded from Elastic
- `data/csv/{date}.csv` — parsed messages per calendar day
- `data/csv_reports_final/` — exported `.xlsx` reports (timestamped, never overwritten)

Notes:

- A report range that contains a day with no parsed CSV is blocked and lists the missing
  days. Parsed partial days (e.g. today so far) are valid and included.
- Elastic downloads that would be truncated by the row limit are split automatically; if a
  one-minute window still hits the limit, the day fails instead of saving partial data.
- Malformed log lines are counted; too many bad lines fail the day instead of silently
  dropping data.

## Build

From `backend/`:

```bat
build.bat
```

Output: `backend/dist/VST.exe` — single file, no Python install needed. Rebuilds replace
`VST.exe` only; `dist/data/` is kept.

## Dev mode (optional, dev machine only)

```bash
cd backend
pip install -r requirements.txt
python -m desktop
```

Uses `backend/data/` (same layout as above, also gitignored).

## Tests

```bash
cd backend
python -m unittest discover -s tests
```

## ACS Log Parser tab

1. **Import & Parse** — download a date range from Elastic into `data/logs/`, then parse
   into `data/csv/`. Already-complete past days are skipped; partial/current days are
   re-downloaded.
2. **Report** — selecting days sets the report range. **Run** previews the pivot;
   **Load more** paginates. **Export** writes the full report to a timestamped `.xlsx`
   under `data/csv_reports_final/`. The workbook has a `Data` sheet, a static `Summary`
   sheet (counts and percentages by `txn_result`), and a native Excel `Pivot` sheet
   built via COM automation when Microsoft Excel is installed (skipped otherwise).

### Custom SQL

Enable **Custom SQL** to edit the query. On first enable, the template from
`db/report_query.sql` is loaded (`%%` -> `%`).

- SQL with `%(date_from)s`, `%(date_to)s`, or `%(txn_id)s` — **From / To / Transaction ID**
  are bound at run time.
- SQL with literal dates — **From / To** still choose which CSV days are loaded.

Custom SQL is restricted to a single `SELECT`/`WITH` statement. File-access functions
(`read_csv`, `read_parquet`, `glob`, ...) and any DDL/DML are rejected.

## 3DS Log Parser tab

Mirrors the ACS Log Parser's **Import & Parse** / **Report** flow for 3DS Server
transactions (keyed by `threeDSServerTransID`, message types AReq/ARes/CReq/CRes/
RReq/RRes/PReq/PRes/Erro), plus a **Raw Log** sub-tab:

1. **Import & Parse** — download a date range from Elastic (`ELASTIC_3DS_APP_NAME`,
   default `solar-3ds-server`; `ELASTIC_3DS_HOSTS`, default `3dss201,3dss202`) into
   `data/logs_3ds/{date}/elastic.log`, then parse into `data/csv_3ds/{date}.csv`. The
   sidebar shows per-day downloaded/parsed status and row counts.
2. **Raw Log** — view the selected day's raw downloaded log text.
3. **Report** — same UX as the ACS Report tab (date range, Transaction ID filter,
   Custom SQL editor, Native pivot, Load more pagination, Export to
   `data/csv_reports_final_3ds/`) except there's no email-sending option yet. The
   `Data` sheet has one row per transaction with its full message timeline, final
   result (`general_success`/`txn_result`), and error/description fields
   (`rreq_result_description` decodes the ACS's human-readable denial reason, e.g.
   `DENIED / CARD_AUTH_FAILED`); the `Summary` sheet is counts/% by `txn_result`.

## Parser tab

Auxiliary utility: number formatting (plain or quoted for SQL) and duplicate checking on
pasted lists. Not part of either log-parsing tool.

## Automation (scheduled daily report)

`app/acs/jobs/daily_report.py` runs the rolling flow unattended: download+parse the last
`DAILY_JOB_DOWNLOAD_DAYS` days (default **2**), build a report over the last
`DAILY_JOB_REPORT_DAYS` days (default **10**), export it, and email it via the local,
already-signed-in Outlook desktop app (COM automation). Older days in the report window
must already have a parsed CSV on disk (from previous runs) — if one is missing, the run
fails loudly instead of emailing a partial report.

**Run it once manually**, from `backend/`:

```bat
python -m desktop --auto-report
```

Same entry point works once `VST.exe` is rebuilt: `VST.exe --auto-report` opens no window,
runs the job, and exits with a status code (0 = ok).

Every run writes `run-summary-*.json` next to the reports (full JSON: days
downloaded/parsed, report path, pivot status, email status, failures) regardless of
success or failure.

### Windows Task Scheduler

`backend/run_auto_report.bat` is the entry point for the scheduled task. It always launches
the **built** `dist\VST.exe --auto-report` (never runs from source) so the scheduled job
uses exactly the code that was last built and tested, sharing the same `dist/data/...`
storage as the exe you use day to day. Rebuild `dist/VST.exe` (`build.bat`) whenever
`backend/` source changes — the scheduled task will not pick up source edits until then.

Create the task (daily at 07:00, only runs while logged in — required for Outlook COM):

```cmd
schtasks /create /tn "VST Daily Report" /tr "\"C:\path\to\backend\run_auto_report.bat\"" /sc daily /st 07:00 /it /f
```

Manage it:

```cmd
schtasks /query /tn "VST Daily Report" /v /fo list   REM inspect current config
schtasks /change /tn "VST Daily Report" /st 08:30     REM change the trigger time
schtasks /run /tn "VST Daily Report"                  REM run right now, on demand
schtasks /change /tn "VST Daily Report" /disable      REM pause
schtasks /change /tn "VST Daily Report" /enable       REM resume
schtasks /delete /tn "VST Daily Report" /f             REM remove entirely
```

(From Git Bash, prefix these with `MSYS_NO_PATHCONV=1` — otherwise it mangles the
`/tn`-style flags.)

Check results: Task Scheduler's **History** tab for the task (started/completed, exit
code), `backend/data/auto_report.log` (full stdout/stderr of every run, appended), or the
`run-summary-*.json` files under `dist/data/csv_reports_final/`.
