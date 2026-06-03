# VST Work Tools

React frontend + FastAPI backend.

## Run

**Docker (recommended)**

```bash
docker compose up --build
```

- UI: http://localhost:5173
- API: http://localhost:8000

**Local**

```bash
cp backend/.env.example backend/.env

cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

The Vite dev server proxies `/api` to the backend, so CORS issues are avoided when using `npm run dev`. Restart the frontend after changing `vite.config.js`.

Large `.log` uploads can be slow through the Vite proxy. For faster uploads locally, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_DIRECT_URL=http://127.0.0.1:8000` (backend CORS already allows this).

## Data layout

All runtime data is stored under `backend/data/` (gitignored):

- `logs/{date}/acs1.log`, `acs2.log` — uploaded ACS logs
- `csv/{date}.csv` — parsed messages per calendar day
- `csv_reports_final/` — report output CSV files

## Use

### Parser tab

Number formatting, duplicate checking, line splitting.

### Logs tab

1. Upload ACS1 and ACS2 `.log` files (drag-and-drop or file picker).
2. Add days to the parse queue from the Coverage sidebar.
3. Click **Parse** — parses logs and saves daily CSV under `data/csv/`. Each date needs both ACS1 and ACS2.
4. **Test 7–11 report** (one-off): **card + merchant** with **≥2 different txns** and **≥2 CRes not Y** (N or empty) in 07:00–11:00. One txn with two bad CRes does not qualify. Full standard report CSV for those pairs. Saved to `data/csv_reports_final/`.
5. Set a date range in Report and click **Run report**. Pick a day in Coverage to fill the range. Export full CSV from the table; a copy is saved under `data/csv_reports_final/`.

### Report CLI

```bash
cd backend
python scripts/build_report.py --mode date --date-from 2026-05-27 --date-to 2026-05-27
```
