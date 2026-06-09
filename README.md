# VST Work Tools

Desktop app (PySide6) for ACS log parsing, daily CSV storage, and DuckDB reports.

## Workflow: dev machine → VDI

**Dev (Cursor):** edit source under `backend/`, commit and push. Do not commit `build/`, `dist/`, or `data/`.

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

Create a desktop shortcut to `backend\dist\VST.exe`. User data stays in `backend\dist\data\` on VDI and is never pushed to git.

## Daily use (VDI)

1. Run `VST.exe` from the shortcut
2. Upload logs → parse → report in the app

Data layout next to the exe:

- `logs/{date}/acs1.log`, `acs2.log` — uploaded ACS logs
- `csv/{date}.csv` — parsed messages per calendar day
- `csv_reports_final/` — exported report CSV files

Optional `dist/.env` beside `VST.exe` can override `LOG_STORAGE_DIR`, `CSV_STORAGE_DIR`, `REPORT_OUTPUT_DIR`.

## Build

From `backend/`:

```bat
build.bat
```

Output: `backend/dist/VST.exe` — single file, no Python install needed.

**Shortcut:** right-click `VST.exe` → *Send to* → *Desktop (create shortcut)*.
Rebuilds replace `VST.exe` only; `dist/data/` is kept.

## Dev mode (optional, dev machine only)

```bash
cd backend
pip install -r requirements.txt
python -m desktop
```

Uses `backend/data/` (same layout as above, also gitignored).

## Parser tab

Number formatting (plain or quoted for SQL) and duplicate checking on pasted lists.

## Logs tab

1. **Upload** ACS1 and ACS2 `.log` files (multi-select).
2. Select saved files and **Add to parse queue** (each date needs both ACS1 and ACS2).
3. **Parse queue** — writes daily CSV under `data/csv/`.
4. Pick a day in **Coverage** to fill the report date range.
5. **Run preview** loads the first 100 rows; **Load more** paginates. **Export CSV** writes the full report via DuckDB `COPY` to `data/csv_reports_final/`.

### Custom SQL

Enable **Custom SQL** to edit the query. On first enable, the template from `db/report_query.sql` is loaded (`%%` → `%`).

- SQL with `%(date_from)s`, `%(date_to)s`, or `%(txn_id)s` — **From / To / Transaction ID** are bound at run time.
- SQL with literal dates — **From / To** still choose which CSV days are loaded; changing dates in the UI can rewrite literal `areq.messagedatetime >= 'YYYY-MM-DD'` filters in the editor.

Use **Filter by transaction ID** for the default template in txn mode (without custom SQL).
