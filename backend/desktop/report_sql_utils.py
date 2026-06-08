from __future__ import annotations

import re

from app.paths import load_report_query_sql
from app.services.report import normalize_date_from, normalize_date_to

DATE_FROM_LITERAL = re.compile(
    r"(areq\.messagedatetime\s*>=\s*')(\d{4}-\d{2}-\d{2})([^']*')",
    re.IGNORECASE,
)
DATE_TO_LITERAL = re.compile(
    r"(areq\.messagedatetime\s*<=\s*')(\d{4}-\d{2}-\d{2})([^']*')",
    re.IGNORECASE,
)


def load_report_template_sql() -> str:
    return load_report_query_sql().replace("%%", "%")


def apply_literal_dates_to_sql(sql: str, date_from: str, date_to: str | None) -> str:
    if not date_from.strip():
        return sql
    from_day = normalize_date_from(date_from)[:10]
    to_value = normalize_date_to(date_to or date_from) or normalize_date_from(date_from)
    to_day = to_value[:10]

    updated = DATE_FROM_LITERAL.sub(rf"\g<1>{from_day}\g<3>", sql, count=1)
    if DATE_TO_LITERAL.search(updated):
        updated = DATE_TO_LITERAL.sub(rf"\g<1>{to_day}\g<3>", updated, count=1)
    return updated
