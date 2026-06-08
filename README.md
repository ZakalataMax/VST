# VST Work Tools

Desktop app (PySide6) for ACS log parsing, daily CSV storage, and DuckDB reports.

## Windows executable

From `backend/`:

```bat
build.bat
```

Or manually:

```bash
pip install -r requirements.txt pyinstaller
pyinstaller vst.spec --noconfirm --clean
```

Output: `backend/dist/VST.exe` — single file, no Python install needed on the target PC.

**Shortcut:** right-click `VST.exe` → *Send to* → *Desktop (create shortcut)*, or drag to the desktop while holding Alt.

**Data:** logs, CSV, and exports are stored in `data/` **next to `VST.exe`** (created on first run). Put the exe in a permanent folder (e.g. `C:\Tools\VST\`) so data stays with it.

Optional `.env` beside `VST.exe` can override `LOG_STORAGE_DIR`, `CSV_STORAGE_DIR`, `REPORT_OUTPUT_DIR`.

```bash
cp backend/.env.example backend/.env

cd backend
pip install -r requirements.txt
python -m desktop
```

Data is stored under `backend/data/` (gitignored):

- `logs/{date}/acs1.log`, `acs2.log` — uploaded ACS logs
- `csv/{date}.csv` — parsed messages per calendar day
- `csv_reports_final/` — exported report CSV files

Override paths via environment variables or `backend/.env`.

## Parser tab

Number formatting (plain or quoted for SQL) and duplicate checking on pasted lists.

## Logs tab

1. **Upload** ACS1 and ACS2 `.log` files (multi-select).
2. Select saved files and **Add to parse queue** (each date needs both ACS1 and ACS2).
3. **Parse queue** — writes daily CSV under `data/csv/`. Re-parse after schema changes (e.g. `browserUserAgent`).
4. Pick a day in **Coverage** to fill the report date range.
5. **Run preview** loads the first 100 rows; **Load more** paginates. **Export CSV** writes the full report via DuckDB `COPY` to `data/csv_reports_final/`.

### Custom SQL

Enable **Custom SQL** to edit the query. On first enable, the template from `db/report_query.sql` is loaded (`%%` → `%`).

- SQL with `%(date_from)s`, `%(date_to)s`, or `%(txn_id)s` — **From / To / Transaction ID** are bound at run time.
- SQL with literal dates (e.g. `samples/select.sql`) — **From / To** still choose which CSV days are loaded; changing dates in the UI can rewrite literal `areq.messagedatetime >= 'YYYY-MM-DD'` filters in the editor.

Use **Filter by transaction ID** for the default template in txn mode (without custom SQL).

## Report CLI

```bash
cd backend
python scripts/build_report.py --mode date --date-from 2026-05-27 --date-to 2026-05-27
```

## Tests

```bash
cd backend
pytest
```
