from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.paths import load_report_query_sql
from app.services.report import run_report_query

router = APIRouter(prefix="/api/report", tags=["report"])


class ReportRunRequest(BaseModel):
    mode: str
    dateFrom: str | None = None
    dateTo: str | None = None
    txnId: str | None = None
    sql: str | None = None
    limit: int = Field(default=500, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)


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
