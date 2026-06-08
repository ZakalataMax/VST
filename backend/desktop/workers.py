from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.parsers.acs_log_parser import parse_log_files
from app.services.csv_storage import save_daily_csvs
from app.services.file_report import export_report_csv, run_report_query
from app.services.log_storage import read_log_files_by_ids, save_upload
from desktop.coverage_utils import sort_log_paths_for_upload


class UploadLogsWorker(QThread):
    progress = Signal(int, int, str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, paths: list[str]) -> None:
        super().__init__()
        self._paths = sort_log_paths_for_upload(paths)

    def run(self) -> None:
        try:
            total = len(self._paths)
            for index, path in enumerate(self._paths, start=1):
                name = Path(path).name
                self.progress.emit(index, total, name)
                content = Path(path).read_bytes()
                save_upload(name, content)
            self.finished_ok.emit()
        except Exception as error:
            self.failed.emit(str(error))


class ParseLogsWorker(QThread):
    progress = Signal(int, int, str)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, file_ids: list[str]) -> None:
        super().__init__()
        self._file_ids = file_ids

    def run(self) -> None:
        try:
            from app.parsers.acs_log_parser import parse_log_files, validate_acs_file_names

            stored = read_log_files_by_ids(self._file_ids)
            file_names = [name for name, _ in stored]
            validate_acs_file_names(file_names)
            self.progress.emit(1, 1, "Parsing logs…")
            rows = parse_log_files(stored)
            saved_days = save_daily_csvs(rows)
            self.finished_ok.emit(saved_days)
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
            result = export_report_csv(**self._kwargs)
            self.finished_ok.emit(result)
        except Exception as error:
            self.failed.emit(str(error))
