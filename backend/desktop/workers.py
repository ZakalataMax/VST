from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.parsers.acs_log_parser import parse_log_files
from app.services.csv_storage import delete_csv_day, save_daily_csvs
from app.services.file_report import export_report_xlsx, run_report_pivot, run_report_query
from app.services.log_storage import delete_log_day, make_file_id, read_log_files_by_ids, save_upload
from desktop.coverage_utils import sort_log_paths_for_upload


@dataclass
class UploadLogsResult:
    saved: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ParseLogsResult:
    saved: list[dict] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


class UploadLogsWorker(QThread):
    progress = Signal(int, int, str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, paths: list[str]) -> None:
        super().__init__()
        self._paths = sort_log_paths_for_upload(paths)

    def run(self) -> None:
        saved: list[dict] = []
        errors: list[str] = []
        total = len(self._paths)
        for index, path in enumerate(self._paths, start=1):
            name = Path(path).name
            self.progress.emit(index, total, name)
            try:
                content = Path(path).read_bytes()
                saved.append(save_upload(name, content))
            except Exception as error:
                errors.append(f"{name}: {error}")
        if not saved and errors:
            self.failed.emit("\n".join(errors))
            return
        self.finished_ok.emit(UploadLogsResult(saved=saved, errors=errors))


class ParseLogsWorker(QThread):
    progress = Signal(int, int, str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, dates: list[str]) -> None:
        super().__init__()
        self._dates = dates

    def run(self) -> None:
        saved_days: list[dict] = []
        failed: dict[str, str] = {}
        total = len(self._dates)
        if total == 0:
            self.finished_ok.emit(ParseLogsResult())
            return

        for index, day_date in enumerate(self._dates, start=1):
            self.progress.emit(index, total, f"Parsing {day_date}…")
            try:
                file_ids = [make_file_id(day_date, node) for node in ("acs1", "acs2")]
                stored = read_log_files_by_ids(file_ids)
                if len(stored) != 2:
                    raise ValueError(f"Missing ACS1 or ACS2 log for {day_date}")
                rows = parse_log_files(stored)
                saved_days.extend(save_daily_csvs(rows))
            except Exception as error:
                failed[day_date] = str(error)

        self.finished_ok.emit(ParseLogsResult(saved=saved_days, failed=failed))


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


class ReportPivotWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, **kwargs) -> None:
        super().__init__()
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = run_report_pivot(**self._kwargs)
            self.finished_ok.emit(result)
        except Exception as error:
            self.failed.emit(str(error))
