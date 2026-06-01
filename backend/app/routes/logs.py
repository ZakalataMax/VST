from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.parsers.acs_log_parser import (
    build_output_file_name,
    parse_log_files,
    read_uploaded_files,
    validate_acs_file_names,
)
from app.parsers.csv_writer import rows_to_csv
from app.parsers.models import CSV_COLUMNS
from app.services.csv_storage import save_daily_csvs
from app.services.log_storage import (
    delete_log_file,
    list_log_days,
    list_log_files,
    read_log_files_by_ids,
    save_upload,
)

router = APIRouter(prefix="/api/logs", tags=["logs"])


class ParseStoredRequest(BaseModel):
    file_ids: list[str] = Field(min_length=1)


async def _read_uploads_async(files: list[UploadFile]) -> tuple[list[tuple[str, bytes]], list[str]]:
    max_total_upload_mb = int(os.getenv("MAX_TOTAL_UPLOAD_MB", "500"))
    max_total_bytes = max_total_upload_mb * 1024 * 1024
    total_bytes = 0
    uploads: list[tuple[str, bytes]] = []
    file_names: list[str] = []

    for file in files:
        file_name = file.filename or "uploaded.log"
        if not file_name.lower().endswith(".log"):
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_name}")
        content_bytes = await file.read()
        total_bytes += len(content_bytes)
        if total_bytes > max_total_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Total upload exceeds {max_total_upload_mb} MB.",
            )
        uploads.append((file_name, content_bytes))
        file_names.append(file_name)

    return uploads, file_names


def _build_parse_response(rows, file_names: list[str]) -> dict:
    csv_text = rows_to_csv(rows)
    output_name = build_output_file_name(rows, file_names)
    saved_csv_days = save_daily_csvs(rows)
    return {
        "columns": CSV_COLUMNS,
        "csv": csv_text,
        "fileName": output_name,
        "savedCsvDays": saved_csv_days,
    }


def _parse_uploads(uploads: list[tuple[str, bytes]], file_names: list[str]) -> dict:
    try:
        validate_acs_file_names(file_names)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    parsed_files = read_uploaded_files(uploads)
    rows = parse_log_files(parsed_files)
    return _build_parse_response(rows, file_names)


@router.post("/upload")
async def upload_logs(files: list[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    uploads, _ = await _read_uploads_async(files)
    saved_files: list[dict] = []
    for file_name, content_bytes in uploads:
        try:
            saved_files.append(save_upload(file_name, content_bytes))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    return {"files": saved_files}


@router.get("/days")
def get_log_days() -> dict:
    return {"days": list_log_days()}


@router.get("/files")
def get_log_files(date: str | None = None) -> dict:
    return {"files": list_log_files(date)}


@router.delete("/files/{file_id:path}")
def remove_log_file(file_id: str) -> dict:
    try:
        delete_log_file(file_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"deleted": True, "id": file_id}


@router.post("/parse")
async def parse_logs(
    files: list[UploadFile] | None = File(None),
    file_ids: str | None = Form(None),
) -> dict:
    if file_ids:
        ids = [value.strip() for value in file_ids.split(",") if value.strip()]
        if not ids:
            raise HTTPException(status_code=400, detail="No log files selected.")
        try:
            stored_files = read_log_files_by_ids(ids)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        file_names = [name for name, _ in stored_files]
        try:
            validate_acs_file_names(file_names)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        rows = parse_log_files(stored_files)
        return _build_parse_response(rows, file_names)

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    uploads, file_names = await _read_uploads_async(files)
    return _parse_uploads(uploads, file_names)


@router.post("/parse/stored")
def parse_stored_logs(body: ParseStoredRequest) -> dict:
    try:
        stored_files = read_log_files_by_ids(body.file_ids)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    file_names = [name for name, _ in stored_files]
    try:
        validate_acs_file_names(file_names)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    rows = parse_log_files(stored_files)
    return _build_parse_response(rows, file_names)
