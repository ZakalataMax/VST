from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QThread, Signal

from app.parsers.acs_log_parser import (
    ParseDiagnostics,
    max_dropped_lines,
    parse_log_files,
)
from app.services.csv_storage import delete_csv_day, save_daily_csvs
from app.services.elastic_logs import ElasticDownloadCancelled, download_day
from app.services.file_report import export_report_xlsx, run_report_query
from app.services.log_storage import (
    delete_log_day,
    read_day_for_parse,
    save_elastic_log,
)


@dataclass
class ElasticDownloadResult:
    saved: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cancelled: bool = False


@dataclass
class ParseLogsResult:
    saved: list[dict] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class ElasticDownloadLogsWorker(QThread):
    progress = Signal(int, int, str)
    day_progress = Signal(int, int, str, int)
    day_saved = Signal(str, int)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, dates: list[str]) -> None:
        super().__init__()
        self._dates = dates
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        saved: list[dict] = []
        errors: list[str] = []
        warnings: list[str] = []
        day_count = len(self._dates)
        for index, day_date in enumerate(self._dates, start=1):
            if self._cancel_requested:
                break
            try:
                result = download_day(
                    day_date,
                    progress=lambda current, total, label, date=day_date, position=index: self.day_progress.emit(
                        position,
                        day_count,
                        date,
                        int(current / total * 100) if total else 0,
                    ),
                    should_cancel=lambda: self._cancel_requested,
                )
                record = save_elastic_log(
                    day_date,
                    result.content,
                    partial=result.partial,
                    row_count=result.row_count,
                    min_datetime=result.min_datetime,
                    max_datetime=result.max_datetime,
                )
                if result.dropped_count:
                    warnings.append(
                        f"{day_date}: skipped {result.dropped_count} row(s) "
                        "with invalid timestamps."
                    )
                saved.append(record)
                self.day_saved.emit(day_date, int(result.row_count or 0))
            except ElasticDownloadCancelled:
                break
            except Exception as error:
                errors.append(f"{day_date}: {error}")
        if self._cancel_requested:
            self.finished_ok.emit(
                ElasticDownloadResult(
                    saved=saved,
                    errors=errors,
                    warnings=warnings,
                    cancelled=True,
                )
            )
            return
        if not saved and errors:
            self.failed.emit("\n".join(errors))
            return
        self.finished_ok.emit(
            ElasticDownloadResult(saved=saved, errors=errors, warnings=warnings)
        )


class ParseLogsWorker(QThread):
    progress = Signal(int, int, str)
    day_progress = Signal(int, int, str, int)
    day_done = Signal(str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, dates: list[str]) -> None:
        super().__init__()
        self._dates = dates

    def run(self) -> None:
        saved_days: list[dict] = []
        failed: dict[str, str] = {}
        warnings: list[str] = []
        total = len(self._dates)
        if total == 0:
            self.finished_ok.emit(ParseLogsResult())
            return

        threshold = max_dropped_lines()
        for index, day_date in enumerate(self._dates, start=1):
            self.day_progress.emit(index, total, day_date, int(index / total * 100))
            try:
                stored = read_day_for_parse(day_date)
                diagnostics = ParseDiagnostics()
                rows = parse_log_files(stored, diagnostics=diagnostics)
                if diagnostics.dropped_count > threshold:
                    failed[day_date] = (
                        f"{diagnostics.dropped_count} malformed line(s) exceeded "
                        f"the allowed threshold ({threshold}). Day not saved."
                    )
                    continue
                saved_days.extend(save_daily_csvs(rows))
                self.day_done.emit(day_date)
                if diagnostics.dropped_count:
                    warnings.append(
                        f"{day_date}: skipped {diagnostics.dropped_count} "
                        "malformed line(s) during parse."
                    )
            except Exception as error:
                failed[day_date] = str(error)

        self.finished_ok.emit(
            ParseLogsResult(saved=saved_days, failed=failed, warnings=warnings)
        )


class DeleteDayWorker(QThread):
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, date: str) -> None:
        super().__init__()
        self._date = date

    def run(self) -> None:
        try:
            delete_log_day(self._date)
            delete_csv_day(self._date)
            self.finished_ok.emit()
        except Exception as error:
            self.failed.emit(str(error))


class ReportRunWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, **kwargs) -> None:
        super().__init__()
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = run_report_query(**self._kwargs)
            self.finished_ok.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class ReportExportWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, **kwargs) -> None:
        super().__init__()
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = export_report_xlsx(**self._kwargs)
            self.finished_ok.emit(result)
        except Exception as error:
            self.failed.emit(str(error))
