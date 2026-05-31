from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")
DB_DIR = ROOT_DIR / "db"

_pools: dict[str, ConnectionPool | None] = {"write": None, "readonly": None}


def get_database_url(readonly: bool = False) -> str | None:
    key = "DATABASE_URL_READONLY" if readonly else "DATABASE_URL"
    return os.getenv(key) or os.getenv("DATABASE_URL")


def _create_pool(readonly: bool) -> ConnectionPool | None:
    url = get_database_url(readonly=readonly)
    if not url:
        return None
    return ConnectionPool(conninfo=url, min_size=1, max_size=5, open=True, kwargs={"row_factory": dict_row})


def get_pool(readonly: bool = False) -> ConnectionPool:
    key = "readonly" if readonly else "write"
    pool = _pools[key]
    if pool is None:
        pool = _create_pool(readonly=readonly)
        if pool is None and readonly:
            pool = _create_pool(readonly=False)
        if pool is None:
            raise RuntimeError("DATABASE_URL is not configured.")
        _pools[key] = pool
    return pool


@contextmanager
def get_connection(readonly: bool = False) -> Iterator[psycopg.Connection]:
    pool = get_pool(readonly=readonly)
    with pool.connection() as connection:
        yield connection


def check_db_connection() -> bool:
    url = get_database_url()
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=3) as connection:
            connection.execute("SELECT 1")
        return True
    except Exception:
        return False


def load_report_query_sql() -> str:
    return (DB_DIR / "report_query.sql").read_text(encoding="utf-8")
