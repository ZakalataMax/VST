from __future__ import annotations


def get_trimmed_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def format_numbers(value: str) -> str:
    return ", ".join(get_trimmed_lines(value))


def format_numbers_with_quotes(value: str) -> str:
    return ",".join(f"'{line}'" for line in get_trimmed_lines(value))


def analyze_duplicates(value: str) -> dict:
    lines = get_trimmed_lines(value)
    seen: set[int] = set()
    duplicate_values: set[int] = set()
    counts: dict[int, int] = {}
    numbers: list[int] = []
    invalid: list[str] = []

    for line in lines:
        try:
            parsed = int(line, 10)
        except ValueError:
            invalid.append(line)
            continue

        if parsed in seen:
            duplicate_values.add(parsed)
        else:
            seen.add(parsed)
        counts[parsed] = counts.get(parsed, 0) + 1
        numbers.append(parsed)

    duplicates = sorted(duplicate_values)
    return {
        "total": len(numbers),
        "unique": len(seen),
        "duplicate_count": len(duplicate_values),
        "duplicates": duplicates,
        "duplicate_occurrences": {value: counts[value] for value in duplicates},
        "invalid": invalid,
    }


def format_duplicate_report(analysis: dict) -> str:
    lines = [
        f"Total numbers: {analysis['total']}",
        f"Unique numbers: {analysis['unique']}",
        f"Duplicates found: {analysis['duplicate_count']}",
        "",
    ]
    if analysis["duplicates"]:
        parts = [
            f"{value} (x{analysis['duplicate_occurrences'].get(value, 0)})"
            for value in analysis["duplicates"]
        ]
        lines.append(f"Duplicate values: {', '.join(parts)}")
    else:
        lines.append("No duplicates found.")
    if analysis["invalid"]:
        lines.append("")
        lines.append(f"Skipped non-numeric lines: {', '.join(analysis['invalid'])}")
    return "\n".join(lines)
