from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

UA_PATTERN = re.compile(r'"browserUserAgent"\s*:\s*"([^"\\]+)"')
AREQ_MARKER = '"messageType":"AReq"'


def count_from_file(path: Path, *, areq_only: bool) -> Counter[str]:
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "browserUserAgent" not in line:
                continue
            if areq_only and AREQ_MARKER not in line:
                continue
            for match in UA_PATTERN.finditer(line):
                counts[match.group(1)] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count unique browserUserAgent values in ACS logs."
    )
    parser.add_argument("logs", nargs="*", type=Path, help="Log file paths")
    parser.add_argument(
        "--areq-only",
        action="store_true",
        help="Only lines containing messageType AReq",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write TSV: count<TAB>user_agent (sorted by count desc, then UA)",
    )
    args = parser.parse_args()

    if not args.logs:
        raise SystemExit("Provide at least one log file path.")

    paths = [p.resolve() for p in args.logs]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise SystemExit(f"Missing files: {', '.join(str(p) for p in missing)}")

    total: Counter[str] = Counter()
    for path in paths:
        file_counts = count_from_file(path, areq_only=args.areq_only)
        print(f"{path.name}: {len(file_counts)} unique UA, {sum(file_counts.values())} occurrences")
        total.update(file_counts)

    print(f"\nCombined: {len(total)} unique browserUserAgent")
    print(f"Total occurrences: {sum(total.values())}\n")

    ranked = sorted(total.items(), key=lambda item: (-item[1], item[0]))
    for ua, count in ranked:
        print(f"{count}\t{ua}")

    if args.output:
        lines = [f"{count}\t{ua}" for ua, count in ranked]
        args.output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        print(f"\nWritten to {args.output}")


if __name__ == "__main__":
    main()
