from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.paths import get_bundle_dir

SERVER_PATTERN = re.compile(
    r"H2H_PCI|Apache-HttpClient|Go-http-client|python-httpx|python-requests|"
    r"curl|Java/|Ktor client|ktor-client|Symfony HttpClient|XML RPC|"
    r"Rapyd 3DS HTTPClient|Fiserv|Borgun|\.NET Framework",
    re.IGNORECASE,
)
IOS_PATTERN = re.compile(
    r"iPhone|iPad|iPod|\biOS\b|iOS[_/ ]|CFNetwork|Darwin|promb2c-ios|"
    r"PUMBOnline.*iPhone|Rozetka.*iOS|rozetka app_version.*iOS|"
    r"NativeApp/iOS|Alamofire|iPhone\d+,\d+|iOS-Webview|targetapp_ios",
    re.IGNORECASE,
)
ANDROID_PATTERN = re.compile(
    r"Android|Dalvik|okhttp|promb2c-android|rozetka_.*android|"
    r"UZ_APP.*Android|EasyPay.*OS: Android|Chrome; AndroidOS",
    re.IGNORECASE,
)
WINDOWS_PATTERN = re.compile(
    r"Windows NT|WindowsNT|Windows\b|Win64|WOW64|MSIE|WindowsApp",
    re.IGNORECASE,
)
MACOS_PATTERN = re.compile(r"Macintosh|Mac OS X|Mac OS|OS X", re.IGNORECASE)
CHROMEOS_PATTERN = re.compile(r"CrOS|ChromeOS", re.IGNORECASE)
LINUX_PATTERN = re.compile(
    r"X11; Linux|Linux x86_64|Linux i686|Konqueror/.*Linux",
    re.IGNORECASE,
)
IPHONE_HARDWARE_ID = re.compile(r"iPhone(\d+),(\d+)", re.IGNORECASE)
IPAD_HARDWARE_ID = re.compile(r"iPad(\d+),(\d+)", re.IGNORECASE)
IPHONE_NAME = re.compile(
    r"\biPhone\s+(SE|\d+(?:\s+(?:Pro(?:\s+Max)?|Plus|mini|Max))?)",
    re.IGNORECASE,
)
IPAD_NAME = re.compile(r"\biPad(?:\s+(Pro|Air|mini|\d+(?:\s+(?:Pro|Air|mini))?))?", re.IGNORECASE)
ANDROID_DEVICE = re.compile(r"Android[^;]*;\s*([^;)]+)", re.IGNORECASE)
SAMSUNG_MODEL = re.compile(r"\b(SM-[A-Z0-9]+)\b", re.IGNORECASE)
ANDROID_BUILD_SUFFIX = re.compile(r"\s+Build/.*$", re.IGNORECASE)
ANDROID_MIUI_SUFFIX = re.compile(r"\s+MIUI/.*$", re.IGNORECASE)
ANDROID_GARBAGE_MODEL = re.compile(
    r"^(?:k|mobile|en|uk-ua|ru-ru|android\s+\d+(?:\.\d+)?|sdk version:\s*\d+)$",
    re.IGNORECASE,
)

IPHONE_HARDWARE: dict[tuple[int, int], str] = {
    (10, 1): "iPhone 8",
    (10, 2): "iPhone 8 Plus",
    (10, 3): "iPhone X",
    (10, 4): "iPhone 8",
    (10, 5): "iPhone 8 Plus",
    (10, 6): "iPhone X",
    (11, 2): "iPhone XS",
    (11, 4): "iPhone XS Max",
    (11, 6): "iPhone XS Max",
    (11, 8): "iPhone XR",
    (12, 1): "iPhone 11",
    (12, 3): "iPhone 11 Pro",
    (12, 5): "iPhone 11 Pro Max",
    (12, 8): "iPhone SE (2nd gen)",
    (13, 1): "iPhone 12 mini",
    (13, 2): "iPhone 12",
    (13, 3): "iPhone 12 Pro",
    (13, 4): "iPhone 12 Pro Max",
    (14, 2): "iPhone 13 Pro",
    (14, 3): "iPhone 13 Pro Max",
    (14, 4): "iPhone 13 mini",
    (14, 5): "iPhone 13",
    (14, 6): "iPhone SE (3rd gen)",
    (14, 7): "iPhone 14",
    (14, 8): "iPhone 14 Plus",
    (15, 2): "iPhone 14 Pro",
    (15, 3): "iPhone 14 Pro Max",
    (15, 4): "iPhone 15",
    (15, 5): "iPhone 15 Plus",
    (16, 1): "iPhone 15 Pro",
    (16, 2): "iPhone 15 Pro Max",
    (17, 1): "iPhone 16 Pro",
    (17, 2): "iPhone 16 Pro Max",
    (17, 3): "iPhone 16",
    (17, 4): "iPhone 16 Plus",
    (17, 5): "iPhone 16e",
}

ANDROID_BRANDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Samsung", re.compile(r"\bSamsung\b|SM-[A-Z0-9]+|GT-[A-Z0-9]+|Galaxy", re.IGNORECASE)),
    ("POCO", re.compile(r"\bPOCO\b", re.IGNORECASE)),
    ("Xiaomi", re.compile(r"Xiaomi|\bMi\s?[A-Z0-9]+|MIX\s?[A-Z0-9]+", re.IGNORECASE)),
    ("Redmi", re.compile(r"\bRedmi\b|\bHM NOTE\b", re.IGNORECASE)),
    ("Huawei", re.compile(r"Huawei|HUAWEI|ANE-[A-Z0-9]+|ELE-[A-Z0-9]+", re.IGNORECASE)),
    ("Honor", re.compile(r"\bHonor\b|COL-[A-Z0-9]+", re.IGNORECASE)),
    ("OPPO", re.compile(r"\bOPPO\b|CPH[0-9]+", re.IGNORECASE)),
    ("OnePlus", re.compile(r"OnePlus|ONEPLUS|GM[0-9]+|IN[0-9]+", re.IGNORECASE)),
    ("Realme", re.compile(r"\bRealme\b|RMX[0-9]+", re.IGNORECASE)),
    ("Motorola", re.compile(r"Motorola|\bmoto\b|XT[0-9]+", re.IGNORECASE)),
    ("Nokia", re.compile(r"\bNokia\b", re.IGNORECASE)),
    ("Tecno", re.compile(r"\bTecno\b", re.IGNORECASE)),
    ("Infinix", re.compile(r"\bInfinix\b", re.IGNORECASE)),
    ("Lenovo", re.compile(r"\bLenovo\b|TB-[A-Z0-9]+", re.IGNORECASE)),
    ("Google", re.compile(r"\bPixel\b", re.IGNORECASE)),
    ("Vivo", re.compile(r"\bvivo\b|V[0-9]{4}", re.IGNORECASE)),
    ("Asus", re.compile(r"\bASUS\b|ASUS_[A-Z0-9_]+|ZenFone", re.IGNORECASE)),
    ("Sony", re.compile(r"\bSony\b|XQ-[A-Z0-9]+", re.IGNORECASE)),
    ("Blackview", re.compile(r"\bBlackview\b|BV[0-9]", re.IGNORECASE)),
)


@dataclass(frozen=True)
class BrowserDeviceInfo:
    os: str
    model: str


def parse_browser_device(raw_user_agent: str | None) -> BrowserDeviceInfo:
    ua = (raw_user_agent or "").replace("\\/", "/").strip()
    if not ua:
        return BrowserDeviceInfo(os="Unknown", model="")
    return _parse_browser_device_cached(ua)


@lru_cache(maxsize=16384)
def _parse_browser_device_cached(ua: str) -> BrowserDeviceInfo:
    if SERVER_PATTERN.search(ua):
        return BrowserDeviceInfo(os="Server/H2H", model="")
    if IOS_PATTERN.search(ua):
        return _parse_ios(ua)
    if ANDROID_PATTERN.search(ua):
        return _parse_android(ua)
    if WINDOWS_PATTERN.search(ua):
        return BrowserDeviceInfo(os="Windows", model="")
    if MACOS_PATTERN.search(ua):
        return BrowserDeviceInfo(os="macOS", model="")
    if CHROMEOS_PATTERN.search(ua):
        return BrowserDeviceInfo(os="ChromeOS", model="")
    if LINUX_PATTERN.search(ua):
        return BrowserDeviceInfo(os="Linux", model="")
    return BrowserDeviceInfo(os="Unknown", model="")


@lru_cache(maxsize=1)
def _android_model_aliases() -> dict[str, str]:
    path = get_bundle_dir() / "app" / "data" / "android_model_aliases.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_marketing_name(name: str) -> str:
    replacements = (
        ("REDMI ", "Redmi "),
        ("XIAOMI ", "Xiaomi "),
        ("POCO ", "POCO "),
        ("realme ", "Realme "),
        ("HONOR ", "Honor "),
        ("HUAWEI ", "Huawei "),
    )
    normalized = name.strip()
    for source, target in replacements:
        if normalized.startswith(source):
            normalized = target + normalized[len(source) :]
            break
    return normalized


def _clean_android_raw_model(raw_model: str) -> str:
    cleaned = ANDROID_BUILD_SUFFIX.sub("", raw_model)
    cleaned = ANDROID_MIUI_SUFFIX.sub("", cleaned)
    return cleaned.strip()


def _is_garbage_android_model(raw_model: str) -> bool:
    return not raw_model or bool(ANDROID_GARBAGE_MODEL.match(raw_model))


def _lookup_android_alias(raw_model: str) -> str:
    alias = _android_model_aliases().get(raw_model.upper())
    if alias:
        return _normalize_marketing_name(alias)
    return ""


def _parse_ios(ua: str) -> BrowserDeviceInfo:
    if re.search(r"iPod", ua, re.IGNORECASE):
        return BrowserDeviceInfo(os="iOS", model="iPod")
    if re.search(r"iPad", ua, re.IGNORECASE):
        return BrowserDeviceInfo(os="iOS", model=_parse_ipad_model(ua))
    return BrowserDeviceInfo(os="iOS", model=_parse_iphone_model(ua))


def _parse_iphone_model(ua: str) -> str:
    name_match = IPHONE_NAME.search(ua)
    if name_match:
        suffix = name_match.group(1).strip()
        if suffix.upper() == "SE":
            return "iPhone SE"
        return f"iPhone {suffix}"
    hardware_match = IPHONE_HARDWARE_ID.search(ua)
    if hardware_match:
        key = (int(hardware_match.group(1)), int(hardware_match.group(2)))
        if key in IPHONE_HARDWARE:
            return IPHONE_HARDWARE[key]
        generation = key[0] - 1
        if generation >= 8:
            return f"iPhone {generation}"
    return ""


def _parse_ipad_model(ua: str) -> str:
    hardware_match = IPAD_HARDWARE_ID.search(ua)
    if hardware_match:
        return f"iPad ({hardware_match.group(1)},{hardware_match.group(2)})"
    name_match = IPAD_NAME.search(ua)
    if name_match:
        suffix = (name_match.group(1) or "").strip()
        if suffix:
            return f"iPad {suffix}".strip()
    return ""


def _parse_android(ua: str) -> BrowserDeviceInfo:
    device_match = ANDROID_DEVICE.search(ua)
    raw_model = device_match.group(1).strip() if device_match else ""
    raw_model = _clean_android_raw_model(raw_model)
    if _is_garbage_android_model(raw_model):
        return BrowserDeviceInfo(os="Android", model="")
    alias = _lookup_android_alias(raw_model)
    if alias:
        return BrowserDeviceInfo(os="Android", model=alias)
    brand = _android_brand(raw_model, ua)
    model = _normalize_android_model(_android_model_label(raw_model, brand), brand)
    return BrowserDeviceInfo(os="Android", model=model)


def _android_brand(raw_model: str, ua: str) -> str:
    haystack = f"{raw_model} {ua}"
    for brand, pattern in ANDROID_BRANDS:
        if pattern.search(haystack):
            return brand
    return ""


def _android_model_label(raw_model: str, brand: str) -> str:
    cleaned = raw_model.strip()
    if brand and not cleaned.upper().startswith(brand.upper()):
        if brand == "Samsung" and SAMSUNG_MODEL.search(cleaned):
            return f"Samsung {cleaned}"
        return f"{brand} {cleaned}".strip()
    return cleaned


def _normalize_android_model(model: str, brand: str) -> str:
    cleaned = model.strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered.startswith("motorola "):
        return "Motorola " + cleaned[9:]
    if brand == "Motorola" and lowered.startswith("moto "):
        return f"Motorola {cleaned}"
    if lowered.startswith("tecno "):
        return "Tecno " + cleaned[6:]
    if lowered.startswith("vivo ") and not cleaned.startswith("Vivo"):
        return "Vivo " + cleaned[5:]
    if lowered.startswith("infinix "):
        return "Infinix " + cleaned[8:]
    if lowered.startswith("redmi ") and not cleaned.startswith("Redmi"):
        return "Redmi " + cleaned[6:]
    return cleaned
