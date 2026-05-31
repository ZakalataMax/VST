from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from app.db import get_connection

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
    "acctNumber": "acctnumber",
    "acquirerBIN": "acquirerbin",
    "browserIP": "browserip",
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

DB_COLUMNS = list(CSV_TO_DB.values())


@dataclass
class ImportResult:
    inserted_rows: int
    deleted_rows: int
    min_date: str
    max_date: str


def _extract_date_part(value: str) -> str | None:
    if not value or len(value) < 10:
        return None
    return value[:10]


def _compute_date_range(rows: list[dict[str, str]]) -> tuple[str, str]:
    dates = sorted(
        {
            part
            for row in rows
            if (part := _extract_date_part(row.get("messageDateTime", "")))
        }
    )
    if not dates:
        raise ValueError("CSV has no messageDateTime values.")
    return dates[0], dates[-1]


def _map_row(row: dict[str, str]) -> list[str]:
    return [row.get(csv_col, "") for csv_col in CSV_TO_DB]


def import_csv_text(csv_text: str) -> ImportResult:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")

    missing = [col for col in CSV_TO_DB if col not in reader.fieldnames]
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

    rows = list(reader)
    if not rows:
        raise ValueError("CSV has no data rows.")

    min_date, max_date = _compute_date_range(rows)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM cust_acs_3dsmess
                WHERE substr(messagedatetime, 1, 10) >= %s
                  AND substr(messagedatetime, 1, 10) <= %s
                """,
                (min_date, max_date),
            )
            deleted_rows = cursor.rowcount

            buffer = io.StringIO()
            writer = csv.writer(buffer, lineterminator="\n")
            for row in rows:
                writer.writerow(_map_row(row))
            buffer.seek(0)

            columns_sql = ", ".join(DB_COLUMNS)
            with cursor.copy(f"COPY cust_acs_3dsmess ({columns_sql}) FROM STDIN WITH (FORMAT csv)") as copy:
                copy.write(buffer.getvalue())

        connection.commit()

    return ImportResult(
        inserted_rows=len(rows),
        deleted_rows=deleted_rows,
        min_date=min_date,
        max_date=max_date,
    )


def _is_full_day_coverage(day: str, min_datetime: str, max_datetime: str) -> bool:
    if len(min_datetime) < 19 or len(max_datetime) < 19:
        return False
    if not min_datetime.startswith(day) or not max_datetime.startswith(day):
        return False
    min_time = min_datetime[11:19]
    max_time = max_datetime[11:19]
    return min_time <= "00:05:00" and max_time >= "23:55:00"


def get_db_days() -> list[dict]:
    with get_connection(readonly=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    substr(messagedatetime, 1, 10) AS log_date,
                    COUNT(*) AS row_count,
                    MIN(messagedatetime) AS min_datetime,
                    MAX(messagedatetime) AS max_datetime
                FROM cust_acs_3dsmess
                WHERE messagedatetime IS NOT NULL AND messagedatetime <> ''
                GROUP BY substr(messagedatetime, 1, 10)
                ORDER BY log_date DESC
                """
            )
            rows = cursor.fetchall()

    days: list[dict] = []
    for row in rows:
        day = row["log_date"]
        min_datetime = row["min_datetime"] or ""
        max_datetime = row["max_datetime"] or ""
        days.append(
            {
                "date": day,
                "rowCount": row["row_count"],
                "minDateTime": min_datetime,
                "maxDateTime": max_datetime,
                "fullDay": _is_full_day_coverage(day, min_datetime, max_datetime),
            }
        )
    return days


def get_db_status() -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS row_count FROM cust_acs_3dsmess")
            count_row = cursor.fetchone()
            cursor.execute(
                """
                SELECT
                    MIN(substr(messagedatetime, 1, 10)) AS min_date,
                    MAX(substr(messagedatetime, 1, 10)) AS max_date
                FROM cust_acs_3dsmess
                WHERE messagedatetime IS NOT NULL AND messagedatetime <> ''
                """
            )
            range_row = cursor.fetchone()

    return {
        "rowCount": count_row["row_count"] if count_row else 0,
        "minDate": range_row["min_date"] if range_row else None,
        "maxDate": range_row["max_date"] if range_row else None,
    }
