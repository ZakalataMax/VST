from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_DIR = ROOT_DIR / "db"


def get_log_storage_dir() -> Path:
    default = ROOT_DIR / "data" / "logs"
    storage_dir = Path(os.getenv("LOG_STORAGE_DIR", str(default)))
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def get_csv_storage_dir() -> Path:
    default = ROOT_DIR / "data" / "csv"
    storage_dir = Path(os.getenv("CSV_STORAGE_DIR", str(default)))
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


def get_report_output_dir() -> Path:
    default = ROOT_DIR / "data" / "csv_reports_final"
    output_dir = Path(os.getenv("REPORT_OUTPUT_DIR", str(default)))
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def load_report_query_sql() -> str:
    return (DB_DIR / "report_query.sql").read_text(encoding="utf-8")
