from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.parsers.csv_writer import rows_to_csv
from app.parsers.models import CSV_COLUMNS, MessageRow
from app.paths import get_csv_storage_dir

CSV_TO_DB: dict[str, str] = {
    "messageDateTime": "messagedatetime",
    "messageType": "messagetype",
    "messageDirection": "messagedirection",
    "threeDSServerTransID": "threedsservertransid",
    "transType": "transtype",
    "transStatus": "transstatus",
    "transStatusReason": "transstatusreason",
    "interactionCounter": "interactioncounter",
    "authenticationMethod": "authenticationmethod",
    "authenticationType": "authenticationtype",
    "eci": "eci",
    "resultsStatus": "resultsstatus",
    "acsCounterAtoS": "acscounteratos",
    "challengeCompletionInd": "challengecompletionind",
    "challengeCancel": "challengecancel",
    "threeDSServerOperatorID": "threedsserveroperatorid",
    "acquirerMerchantID": "acquirermerchantid",
    "merchantName": "merchantname",
    "acctNumber": "acctnumber",
    "acquirerBIN": "acquirerbin",
    "browserIP": "browserip",
    "browserUserAgent": "browseruseragent",
    "errorCode": "errorcode",
    "isChallengeExpired": "ischallengeexpired",
    "oobResultStatus": "oobresultstatus",
    "oobResultMethod": "oobresultmethod",
    "challengeMethod": "challengemethod",
    "challengeMethodCode": "challengemethodcode",
    "isChallengeSucceeded": "ischallengesucceeded",
    "challengeSubmit": "challengesubmit",
    "authMethodSwitch": "authmethodswitch",
    "creqIncoming": "creqincoming",
}


@dataclass
class CsvDaySummary:
    date: str
    row_count: int
    min_datetime: str
    max_datetime: str
    full_day: bool


def _extract_date_part(value: str) -> str | None:
    if not value or len(value) < 10:
        return None
    return value[:10]


def _is_full_day_coverage(day: str, min_datetime: str, max_datetime: str) -> bool:
    if len(min_datetime) < 19 or len(max_datetime) < 19:
        return False
    if not min_datetime.startswith(day) or not max_datetime.startswith(day):
        return False
    min_time = min_datetime[11:19]
    max_time = max_datetime[11:19]
    return min_time <= "00:05:00" and max_time >= "23:55:00"


def _summarize_rows(day_rows: list[MessageRow]) -> tuple[int, str, str]:
    datetimes = [row.message_datetime for row in day_rows if row.message_datetime]
    if not datetimes:
        return 0, "", ""
    sorted_times = sorted(datetimes)
    return len(day_rows), sorted_times[0], sorted_times[-1]


def _write_meta(csv_dir: Path, day: str, row_count: int, min_datetime: str, max_datetime: str) -> None:
    meta_path = csv_dir / f"{day}.meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "rowCount": row_count,
                "minDateTime": min_datetime,
                "maxDateTime": max_datetime,
                "fullDay": _is_full_day_coverage(day, min_datetime, max_datetime),
            }
        ),
        encoding="utf-8",
    )


def _read_meta(csv_dir: Path, day: str) -> dict | None:
    meta_path = csv_dir / f"{day}.meta.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _load_meta_from_csv(csv_path: Path, day: str) -> dict:
    min_datetime = ""
    max_datetime = ""
    row_count = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_count += 1
            value = row.get("messageDateTime", "")
            if not value:
                continue
            if not min_datetime or value < min_datetime:
                min_datetime = value
            if not max_datetime or value > max_datetime:
                max_datetime = value
    return {
        "rowCount": row_count,
        "minDateTime": min_datetime,
        "maxDateTime": max_datetime,
        "fullDay": _is_full_day_coverage(day, min_datetime, max_datetime),
    }


def save_daily_csvs(rows: list[MessageRow]) -> list[dict]:
    csv_dir = get_csv_storage_dir()
    by_day: dict[str, list[MessageRow]] = defaultdict(list)

    for row in rows:
        day = _extract_date_part(row.message_datetime)
        if not day:
            continue
        by_day[day].append(row)

    if not by_day:
        raise ValueError("Parsed rows have no messageDateTime values.")

    saved_days: list[dict] = []
    for day in sorted(by_day):
        day_rows = by_day[day]
        csv_path = csv_dir / f"{day}.csv"
        csv_path.write_text(rows_to_csv(day_rows), encoding="utf-8")
        row_count, min_datetime, max_datetime = _summarize_rows(day_rows)
        _write_meta(csv_dir, day, row_count, min_datetime, max_datetime)
        saved_days.append(
            {
                "date": day,
                "rowCount": row_count,
                "minDateTime": min_datetime,
                "maxDateTime": max_datetime,
                "fullDay": _is_full_day_coverage(day, min_datetime, max_datetime),
            }
        )

    return saved_days


def list_csv_days() -> list[dict]:
    csv_dir = get_csv_storage_dir()
    days: list[dict] = []

    for csv_path in sorted(csv_dir.glob("*.csv"), key=lambda path: path.stem, reverse=True):
        day = csv_path.stem
        meta = _read_meta(csv_dir, day)
        if meta is None:
            meta = _load_meta_from_csv(csv_path, day)
            _write_meta(csv_dir, day, meta["rowCount"], meta["minDateTime"], meta["maxDateTime"])
        days.append({"date": day, **meta})

    return days


def resolve_csv_paths_for_dates(dates: list[str]) -> list[Path]:
    csv_dir = get_csv_storage_dir()
    paths: list[Path] = []
    missing: list[str] = []

    for day in dates:
        path = csv_dir / f"{day}.csv"
        if path.exists():
            paths.append(path)
        else:
            missing.append(day)

    if not paths:
        if missing:
            raise ValueError(f"No CSV for date(s): {', '.join(missing)}")
        raise ValueError("No parsed CSV files found.")

    return paths


def delete_csv_day(day: str) -> None:
    csv_dir = get_csv_storage_dir()
    (csv_dir / f"{day}.csv").unlink(missing_ok=True)
    (csv_dir / f"{day}.meta.json").unlink(missing_ok=True)


def list_all_csv_paths() -> list[Path]:
    csv_dir = get_csv_storage_dir()
    paths = sorted(csv_dir.glob("*.csv"), key=lambda path: path.stem)
    if not paths:
        raise ValueError("No parsed CSV files found.")
    return paths
