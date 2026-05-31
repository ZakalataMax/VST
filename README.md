# VST Work Tools

Internal utility app with a React frontend and a FastAPI backend.

- **Parser** — client-side number formatting, duplicate checking, line splitting
- **Logs** — placeholder for upcoming log tools

## Project structure

```
VST/
├── frontend/          React + Vite
├── backend/           FastAPI
│   └── samples/       sample log files for development
└── docker-compose.yml
```

## Prerequisites

- **Local:** Node.js 22+, Python 3.12+
- **Docker:** Docker Desktop with Docker Compose

## Local development

Frontend and backend run as separate processes.

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000  
Health check: http://localhost:8000/api/health

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173

Optional env var for API URL (default is `http://localhost:8000`):

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Docker

Each service starts independently:

```bash
docker compose up backend
```

```bash
docker compose up frontend
```

Rebuild after dependency changes:

```bash
docker compose build backend
docker compose build frontend
```

## Production build (frontend only)

```bash
cd frontend
npm run build
npm run preview
```

Output goes to `frontend/dist/`.
