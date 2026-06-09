from __future__ import annotations

import re

from app.paths import load_report_query_sql
from app.services.report import normalize_date_from, normalize_date_to

TXN_FILTER_LINE = re.compile(
    r"\(\s*%\(txn_id\)s::text\s+IS\s+NULL\s+OR\s+areq\.threedsservertransid\s*=\s*%\(txn_id\)s::text\s*\)",
    re.IGNORECASE,
)
TXN_FILTER_LITERAL = re.compile(
    r"\(\s*areq\.threedsservertransid\s*=\s*'(?:[^']|'')*'\s*\)",
    re.IGNORECASE,
)


def load_report_template_sql() -> str:
    return load_report_query_sql().replace("%%", "%")


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def apply_literal_dates_to_sql(sql: str, date_from: str, date_to: str | None) -> str:
    if not date_from.strip():
        return sql
    from_value = _sql_literal(normalize_date_from(date_from))
    to_value = normalize_date_to(date_to or date_from) or normalize_date_from(date_from)
    to_literal = _sql_literal(to_value)

    updated = re.sub(
        r"(areq\.messagedatetime\s*>=\s*')([^']*)(')",
        rf"\g<1>{from_value}\g<3>",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )
    updated = re.sub(
        r"(areq\.messagedatetime\s*<=\s*')([^']*)(')",
        rf"\g<1>{to_literal}\g<3>",
        updated,
        count=1,
        flags=re.IGNORECASE,
    )
    if "%(date_from)s" in updated:
        updated = updated.replace("%(date_from)s::text", f"'{from_value}'")
        updated = updated.replace(
            "(%(date_to)s::text IS NULL OR areq.messagedatetime <= %(date_to)s::text)",
            f"(areq.messagedatetime <= '{to_literal}')",
        )
    return updated


def _strip_txn_filter(sql: str) -> str:
    updated = TXN_FILTER_LINE.sub("", sql)
    updated = TXN_FILTER_LITERAL.sub("", updated)
    updated = re.sub(r"WHERE\s+AND", "WHERE", updated, flags=re.IGNORECASE)
    updated = re.sub(r"\n[ \t]+AND[ \t]+\n", "\n", updated)
    return updated


def build_report_sql_from_filters(
    *,
    date_from: str,
    date_to: str,
    txn_id: str = "",
    filter_by_txn: bool = False,
) -> str:
    sql = load_report_template_sql()
    sql = apply_literal_dates_to_sql(sql, date_from, date_to)

    if filter_by_txn:
        if txn_id.strip():
            txn_value = txn_id.strip().replace("'", "''")
            replacement = f"(areq.threedsservertransid = '{txn_value}')"
            if TXN_FILTER_LINE.search(sql):
                sql = TXN_FILTER_LINE.sub(replacement, sql, count=1)
            elif TXN_FILTER_LITERAL.search(sql):
                sql = TXN_FILTER_LITERAL.sub(replacement, sql, count=1)
            else:
                sql = re.sub(
                    r"(WHERE\s+)",
                    rf"\1{replacement}\n  AND ",
                    sql,
                    count=1,
                    flags=re.IGNORECASE,
                )
        return sql.strip()

    return _strip_txn_filter(sql).strip()
