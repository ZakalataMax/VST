from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

URL_PATTERN = re.compile(r'"threeDSServerURL"\s*:\s*"([^"\\]+)"')
AREQ_MARKER = '"messageType":"AReq"'


def extract_urls_from_file(path: Path, *, areq_only: bool) -> set[str]:
    urls: set[str] = set()
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "threeDSServerURL" not in line:
                continue
            if areq_only and AREQ_MARKER not in line:
                continue
            for match in URL_PATTERN.finditer(line):
                urls.add(match.group(1))
    return urls


def normalize_base_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme:
        return url
    path = parsed.path.rstrip("/") or ""
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract unique threeDSServerURL values from ACS logs.")
    parser.add_argument(
        "logs",
        nargs="*",
        type=Path,
        help="Log file paths (default: May 20-29 ACS1+ACS2 samples)",
    )
    parser.add_argument(
        "--areq-only",
        action="store_true",
        help="Only lines containing messageType AReq",
    )
    parser.add_argument(
        "--normalize-base",
        action="store_true",
        help="Collapse to scheme + host + path (strip query and trailing slash)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write sorted URLs to this file",
    )
    args = parser.parse_args()

    if args.logs:
        paths = [p.resolve() for p in args.logs]
    else:
        samples = Path(__file__).resolve().parents[1] / "samples"
        paths = sorted(samples.glob("ACS*_common.2026-05-*.log"))

    missing = [p for p in paths if not p.is_file()]
    if missing:
        raise SystemExit(f"Missing files: {', '.join(str(p) for p in missing)}")

    all_urls: set[str] = set()
    per_file: list[tuple[str, int]] = []

    for path in paths:
        found = extract_urls_from_file(path, areq_only=args.areq_only)
        per_file.append((path.name, len(found)))
        all_urls |= found

    if args.normalize_base:
        all_urls = {normalize_base_url(url) for url in all_urls}

    sorted_urls = sorted(all_urls)

    print(f"Files scanned: {len(paths)}")
    if args.areq_only:
        print("Filter: AReq lines only")
    if args.normalize_base:
        print("Mode: normalized base URL (scheme + host + path)")
    for name, count in per_file:
        print(f"  {name}: {count} unique URL(s) in file")
    print(f"\nTotal unique threeDSServerURL: {len(sorted_urls)}\n")

    if args.output:
        args.output.write_text("\n".join(sorted_urls) + ("\n" if sorted_urls else ""), encoding="utf-8")
        print(f"Written to {args.output}")
    else:
        for url in sorted_urls:
            print(url)


if __name__ == "__main__":
    main()
