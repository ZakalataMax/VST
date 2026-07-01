from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

BRAND_FILES = [
    "xiaomi_en.md",
    "samsung_global_en.md",
    "oppo_global_en.md",
    "realme_global_en.md",
    "oneplus_en.md",
    "honor_global_en.md",
    "huawei_global_en.md",
    "blackshark_en.md",
    "vivo_global_en.md",
    "asus_en.md",
]
BASE = "https://raw.githubusercontent.com/KHwang9883/MobileModels/master/brands/"
CODE_PATTERN = re.compile(r"`([A-Z0-9]+)`:\s*([^\n`]+)")
REGION_SUFFIXES = (
    r"\s+Global\s*\(NFC\)$",
    r"\s+Global\s*\([^)]+\)$",
    r"\s+Global$",
    r"\s+India$",
    r"\s+China$",
    r"\s+Japan$",
    r"\s+Europe$",
    r"\s+Russia$",
    r"\s+Indonesia$",
    r"\s+Turkey$",
    r"\s+Taiwan$",
    r"\s+Latin America.*$",
    r"\s+Southeast Asia$",
    r"\s+International$",
    r"\s+Carrier$",
)


def clean_name(name: str) -> str:
    cleaned = name.strip()
    if " / " in cleaned:
        cleaned = cleaned.split(" / ", 1)[0].strip()
    for pattern in REGION_SUFFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def main() -> None:
    aliases: dict[str, str] = {}
    for filename in BRAND_FILES:
        url = BASE + filename
        text = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
        for code, name in CODE_PATTERN.findall(text):
            aliases[code.upper()] = clean_name(name)

    out = Path(__file__).resolve().parents[1] / "app" / "data" / "android_model_aliases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(aliases, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote {len(aliases)} aliases to {out}")


if __name__ == "__main__":
    main()
