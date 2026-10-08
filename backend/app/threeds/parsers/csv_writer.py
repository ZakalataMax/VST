from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Iterable, TextIO

from app.common.device_detection import parse_browser_device
from app.threeds.parsers.models import CSV_COLUMNS, ThreeDsMessageRow

CSV_DELIMITER = os.getenv("CSV_DELIMITER", ";")


def csv_dict_writer(handle: TextIO, fieldnames: list[str], **kwargs) -> csv.DictWriter:
    return csv.DictWriter(
        handle,
        fieldnames=fieldnames,
        delimiter=CSV_DELIMITER,
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
        extrasaction=kwargs.pop("extrasaction", "raise"),
        **kwargs,
    )


def duckdb_read_csv_delim() -> str:
    return CSV_DELIMITER.replace("'", "''")


def _csv_row_dict(row: ThreeDsMessageRow) -> dict[str, str]:
    data = row.to_csv_dict()
    user_agent = data.get("browserUserAgent", "")
    if user_agent:
        device = parse_browser_device(user_agent)
        data["browserOS"] = device.os
        data["browserModel"] = device.model
    else:
        data["browserOS"] = ""
        data["browserModel"] = ""
    return data


def write_rows_csv(path: Path, rows: Iterable[ThreeDsMessageRow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv_dict_writer(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_csv_row_dict(row))


def rows_to_csv(rows: Iterable[ThreeDsMessageRow]) -> str:
    output = io.StringIO()
    writer = csv_dict_writer(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(_csv_row_dict(row))
    return output.getvalue()
