from __future__ import annotations

from fastapi import APIRouter

from app.services.csv_storage import list_csv_days

router = APIRouter(prefix="/api/csv", tags=["csv"])


@router.get("/days")
def get_csv_days() -> dict:
    return {"days": list_csv_days()}
