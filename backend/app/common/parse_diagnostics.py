from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_MAX_DROPPED_LINES = 100


@dataclass
class ParseDiagnostics:
    dropped_count: int = 0
    samples: list[str] = field(default_factory=list)

    def record_drop(self, reason: str) -> None:
        self.dropped_count += 1
        if len(self.samples) < 10:
            self.samples.append(reason)


def max_dropped_lines() -> int:
    raw = os.getenv("PARSER_MAX_DROPPED", "")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_DROPPED_LINES
    return value if value >= 0 else DEFAULT_MAX_DROPPED_LINES
