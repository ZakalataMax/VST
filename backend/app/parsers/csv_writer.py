from __future__ import annotations

import csv
import io
import json
from typing import Iterable

from app.parsers.models import CSV_COLUMNS, MessageRow


def rows_to_csv(rows: Iterable[MessageRow]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.to_csv_dict())
    return output.getvalue()
