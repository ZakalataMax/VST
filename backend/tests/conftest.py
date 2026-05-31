from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"
REFERENCE_CSV = SAMPLES_DIR / "3ds-messages-acs1-acs2-2026-05-27-to-2026-05-29-spec-aligned.csv"
SAMPLE_TXN_ID = "abd28639-24f2-49aa-9e1b-541391c4d5b3"


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is not set")
    try:
        with psycopg.connect(url, connect_timeout=3) as connection:
            connection.execute("SELECT 1")
    except Exception as error:
        pytest.skip(f"Database unavailable: {error}")
    return url


@pytest.fixture
def reset_table(database_url: str) -> None:
    with psycopg.connect(database_url) as connection:
        connection.execute("TRUNCATE cust_acs_3dsmess")
        connection.commit()


@pytest.fixture
def sample_csv_text() -> str:
    if not REFERENCE_CSV.exists():
        pytest.skip("Reference CSV sample is missing.")
    lines = REFERENCE_CSV.read_text(encoding="utf-8-sig").splitlines()
    return "\n".join(lines[:2001]) + "\n"
