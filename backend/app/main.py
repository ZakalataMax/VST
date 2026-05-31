from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import check_db_connection
from app.routes.db import router as db_router
from app.routes.logs import router as logs_router
from app.routes.report import router as report_router

app = FastAPI(title="VST API")

app.include_router(logs_router)
app.include_router(db_router)
app.include_router(report_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    db_ok = check_db_connection()
    return {"status": "ok", "database": "ok" if db_ok else "unavailable"}
