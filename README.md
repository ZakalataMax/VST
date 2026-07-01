# VST Work Tools

Desktop app (PySide6) for downloading ACS logs from Elastic, parsing them into daily
CSV tables, building DuckDB pivot reports, and exporting them to Excel.

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
`ELASTIC_HOSTS`, `ELASTIC_VERIFY_TLS`, `ELASTIC_CA_BUNDLE`, `LOG_STORAGE_DIR`,
`CSV_STORAGE_DIR`, `REPORT_OUTPUT_DIR`. See `.env.example` for the full list.

Storing `.env` next to the exe on a trusted single-user VDI is an intentional choice for
this internal tool.

## Daily use (VDI)

1. Run `VST.exe` from the shortcut. The app opens on the **Logs** tab.
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

## Parser tab

Auxiliary utility: number formatting (plain or quoted for SQL) and duplicate checking on
pasted lists. Not part of the main import/parse/report flow.

## Logs tab

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

## Future automation

A scheduled CLI worker is planned to run the rolling daily flow unattended (download the
last full days plus the current day so far, parse, build the report, and email it via
SMTP). It will reuse the same services as the desktop app.
