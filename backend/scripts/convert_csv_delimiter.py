from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.parsers.csv_writer import CSV_DELIMITER, dict_rows_to_csv


def convert_file(
    input_path: Path,
    output_path: Path | None = None,
    source_delimiter: str = ",",
) -> Path:
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=source_delimiter)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")
        columns = list(reader.fieldnames)
        rows = list(reader)

    target = output_path or input_path
    target.write_text(dict_rows_to_csv(columns, rows), encoding="utf-8-sig")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert CSV to Excel-friendly delimiter (default semicolon).")
    parser.add_argument("input", type=Path, help="Input CSV path")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output path (default: overwrite input)")
    parser.add_argument(
        "--from-delimiter",
        default=",",
        help="Source delimiter when auto-detect is wrong (default: comma)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"File not found: {args.input}", file=sys.stderr)
        return 1

    target = convert_file(args.input, args.output, args.from_delimiter)
    print(f"Wrote {target} ({len(target.read_text(encoding='utf-8-sig').splitlines()) - 1} rows, delimiter={CSV_DELIMITER!r})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
