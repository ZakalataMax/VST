from __future__ import annotations

import os
from pathlib import Path

from app.common.paths import DB_DIR, ROOT_DIR


def get_log_storage_dir() -> Path:
    default = ROOT_DIR / "data" / "logs_3ds"
    storage_dir = Path(os.getenv("THREEDS_LOG_STORAGE_DIR", str(default)))
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def get_csv_storage_dir() -> Path:
    default = ROOT_DIR / "data" / "csv_3ds"
    storage_dir = Path(os.getenv("THREEDS_CSV_STORAGE_DIR", str(default)))
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def get_report_output_dir() -> Path:
    default = ROOT_DIR / "data" / "csv_reports_final_3ds"
    output_dir = Path(os.getenv("THREEDS_REPORT_OUTPUT_DIR", str(default)))
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def load_report_query_sql() -> str:
    return (DB_DIR / "report_query_3ds.sql").read_text(encoding="utf-8")
