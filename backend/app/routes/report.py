from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.paths import get_report_output_dir, load_report_query_sql
from app.services.file_report import export_report_csv
from app.services.report import run_report_query

router = APIRouter(prefix="/api/report", tags=["report"])

EXPORT_FILE_PATTERN = re.compile(r"^report[-0-9a-zA-Z.]+\.csv$")


class ReportRunRequest(BaseModel):
    mode: str
    dateFrom: str | None = None
    dateTo: str | None = None
    txnId: str | None = None
    sql: str | None = None
    limit: int = Field(default=500, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)


class ReportExportRequest(BaseModel):
    mode: str
    dateFrom: str | None = None
    dateTo: str | None = None
    txnId: str | None = None
    sql: str | None = None


@router.get("/template")
def report_template() -> dict[str, str]:
    return {"sql": load_report_query_sql().replace("%%", "%")}


@router.post("/run")
def run_report(body: ReportRunRequest) -> dict:
    try:
        result = run_report_query(
            mode=body.mode,
            date_from=body.dateFrom,
            date_to=body.dateTo,
            txn_id=body.txnId,
            sql=body.sql,
            limit=body.limit,
            offset=body.offset,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Report failed: {error}") from error

    return {
        "columns": result.columns,
        "rows": result.rows,
        "rowCount": result.row_count,
        "limit": result.limit,
        "offset": result.offset,
    }


@router.post("/export")
def export_report(body: ReportExportRequest) -> dict:
    try:
        result = export_report_csv(
            mode=body.mode,
            date_from=body.dateFrom,
            date_to=body.dateTo,
            txn_id=body.txnId,
            sql=body.sql,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Export failed: {error}") from error

    return {
        "fileName": result.file_name,
        "rowCount": result.row_count,
        "columns": result.columns,
    }


@router.get("/export/{file_name}")
def download_export(file_name: str) -> FileResponse:
    if not EXPORT_FILE_PATTERN.match(file_name):
        raise HTTPException(status_code=404, detail="Export file not found.")
    path = get_report_output_dir() / file_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found.")
    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename=file_name,
    )
