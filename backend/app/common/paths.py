from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", get_app_root()))
    return Path(__file__).resolve().parents[2]


ROOT_DIR = get_app_root()
DB_DIR = get_bundle_dir() / "db"
