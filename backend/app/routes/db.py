from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.csv_import import get_db_days, get_db_status, import_csv_text

router = APIRouter(prefix="/api/db", tags=["db"])


@router.get("/days")
def db_days() -> dict:
    try:
        return {"days": get_db_days()}
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Database error: {error}") from error


@router.get("/status")
def db_status() -> dict:
    try:
        return get_db_status()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Database error: {error}") from error


@router.post("/import")
async def import_csv(file: UploadFile = File(...)) -> dict:
    file_name = file.filename or "uploaded.csv"
    if not file_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_name}")

    csv_bytes = await file.read()
    try:
        csv_text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.") from error

    try:
        result = import_csv_text(csv_text)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Import failed: {error}") from error

    return {
        "insertedRows": result.inserted_rows,
        "deletedRows": result.deleted_rows,
        "minDate": result.min_date,
        "maxDate": result.max_date,
    }
