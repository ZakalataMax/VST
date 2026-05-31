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
docker compose up postgres -d
cp backend/.env.example backend/.env

cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

## Use

### Parser tab

Number formatting, duplicate checking, line splitting.

### Logs tab

1. Upload ACS1 and ACS2 `.log` files (drag-and-drop or file picker).
2. Add days to the parse queue from the Coverage sidebar.
3. Click **Parse & Import** — parses logs, imports CSV into PostgreSQL. Each date needs both ACS1 and ACS2.
4. Set a date range in Report and click **Run report**. Pick a day in Coverage to fill the range. Export full CSV from the table.
