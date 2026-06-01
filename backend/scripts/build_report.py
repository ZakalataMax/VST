from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")

from app.paths import get_report_output_dir
from app.services.report import run_report_query


def main() -> int:
    parser = argparse.ArgumentParser(description="Build report CSV from parsed daily CSV files.")
    parser.add_argument("--mode", choices=["date", "txnId"], default="date")
    parser.add_argument("--date-from", dest="date_from", default="")
    parser.add_argument("--date-to", dest="date_to", default="")
    parser.add_argument("--txn-id", dest="txn_id", default="")
    args = parser.parse_args()

    if args.mode == "date" and not args.date_from.strip():
        print("date-from is required for date mode.", file=sys.stderr)
        return 1
    if args.mode == "txnId" and not args.txn_id.strip():
        print("txn-id is required for txnId mode.", file=sys.stderr)
        return 1

    result = run_report_query(
        mode=args.mode,
        date_from=args.date_from or None,
        date_to=args.date_to or None,
        txn_id=args.txn_id or None,
        limit=1,
        offset=0,
    )

    output_dir = get_report_output_dir()
    candidates = sorted(output_dir.glob("report-*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        print("Report file was not created.", file=sys.stderr)
        return 1

    print(candidates[0])
    print(f"rows={result.row_count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
