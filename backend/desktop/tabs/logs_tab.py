from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.paths import get_report_output_dir
from app.services.report import validate_report_range
from app.services.csv_storage import list_csv_days
from app.services.csv_storage import delete_csv_day
from app.services.log_storage import list_log_days, list_log_files, scan_log_datetime_range
from desktop.coverage_utils import (
    STATUS_READY,
    build_coverage_days,
)
from desktop.report_sql_utils import apply_literal_dates_to_sql
from desktop.widgets.coverage_sidebar import CoverageSidebar
from desktop.widgets.import_parse_panel import ImportParsePanel
from desktop.widgets.report_panel import ReportPanel
from desktop.workers import (
    DeleteDayWorker,
    ParseLogsWorker,
    ReportExportWorker,
    ReportRunWorker,
    UploadLogsWorker,
)

CHUNK_SIZE = 100


def _missing_acs_nodes(log_day: dict) -> list[str]:
    return [node.upper() for node in ("acs1", "acs2") if not log_day.get(node)]


class LogsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._files: list[dict] = []
        self._coverage_days: list[dict] = []
        self._syncing_selection = False
        self._selected_dates: list[str] = []
        self._report_columns: list[str] = []
        self._report_rows: list[dict] = []
        self._report_offset = 0
        self._report_total = 0
        self._active_worker = None
        self._parsing_dates: set[str] = set()
        self._failed_dates: dict[str, str] = {}
        self._import_skip_messages: list[str] = []
        self._last_upload_date = ""
        self._last_worker_error = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = CoverageSidebar()
        self.sidebar.days_selected.connect(self._on_sidebar_days_selected)
        root.addWidget(self.sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_parse_tab(), "Import & Parse")
        self.tabs.addTab(self._build_report_tab(), "Report")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        content_layout.addWidget(self.tabs, stretch=1)
        root.addWidget(content, stretch=1)

        self.refresh_data()

    def _build_parse_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.import_panel = ImportParsePanel()
        self.import_panel.load_requested.connect(self._upload_logs)
        self.import_panel.files_dropped.connect(self._upload_paths)
        self.import_panel.delete_requested.connect(self._delete_day)
        layout.addWidget(self.import_panel)
        return tab

    def _build_report_tab(self) -> QWidget:
        self.report_panel = ReportPanel()
        self.report_panel.run_requested.connect(self._run_report)
        self.report_panel.export_requested.connect(self._export_report)
        self.report_panel.load_more_requested.connect(self._load_more_report)
        return self.report_panel

    def refresh_data(self) -> None:
        try:
            self._files = list_log_files()
            log_days = list_log_days()
            csv_days = list_csv_days()
            self._coverage_days = build_coverage_days(
                self._files,
                log_days,
                csv_days,
                parsing_dates=self._parsing_dates,
                failed_dates=self._failed_dates,
            )
            self._render_views()
        except Exception as error:
            QMessageBox.critical(self, "Refresh failed", str(error))

    def _render_views(self) -> None:
        self.sidebar.set_days(self._coverage_days)
        days = [self._day_by_date(date) for date in self._selected_dates]
        days = [day for day in days if day]
        if not days and self._coverage_days:
            default_day = self._default_selection_day()
            days = [default_day] if default_day else []
        self._apply_days_selection(days)

    def _default_selection_day(self) -> dict | None:
        for target in (
            (date.today() - timedelta(days=1)).isoformat(),
            date.today().isoformat(),
        ):
            day = self._day_by_date(target)
            if day:
                return day
        if self._last_upload_date:
            day = self._day_by_date(self._last_upload_date)
            if day:
                return day
        return self._coverage_days[0] if self._coverage_days else None

    def _day_by_date(self, date: str) -> dict | None:
        if not date:
            return None
        return next((item for item in self._coverage_days if item["date"] == date), None)

    def _apply_days_selection(self, days: list[dict]) -> None:
        self._syncing_selection = True
        dates = [day["date"] for day in days]
        self._selected_dates = dates
        self.sidebar.set_selected_dates(dates)
        self.import_panel.set_days(days)
        self._sync_report_dates(dates)
        self._syncing_selection = False

    def _sync_report_dates(self, dates: list[str]) -> None:
        if not dates:
            return
        sorted_dates = sorted(dates)
        self.report_panel.set_date_range(sorted_dates[0], sorted_dates[-1])

    def _select_days(self, dates: list[str]) -> None:
        days = [self._day_by_date(date) for date in dates]
        days = [day for day in days if day]
        self._apply_days_selection(days)

    def _select_day(self, date: str) -> None:
        self._select_days([date])

    def _on_sidebar_days_selected(self, dates: list[str]) -> None:
        if self._syncing_selection:
            return
        if not dates:
            self._apply_days_selection([])
            return
        self._select_days(dates)

    def _open_report_for_date(self, date: str) -> None:
        self._select_day(date)
        self.tabs.setCurrentIndex(1)

    def _parse_ready(self) -> None:
        dates = [day["date"] for day in self._coverage_days if day.get("status") == STATUS_READY]
        self._parse_dates(dates)

    def _parse_day(self, date: str) -> None:
        self._parse_dates([date])

    def _split_parseable_dates(self, dates: list[str]) -> tuple[list[str], list[str]]:
        day_by_date = {day["date"]: day for day in self._coverage_days}
        parseable: list[str] = []
        skip_messages: list[str] = []
        for date in sorted(dates):
            day = day_by_date.get(date)
            if not day:
                continue
            log_day = day.get("log_day") or {}
            missing = _missing_acs_nodes(log_day)
            if missing:
                skip_messages.append(
                    f"{date}: missing {', '.join(missing)} log — parsing skipped"
                )
                continue
            parseable.append(date)
        return parseable, skip_messages

    def _parse_dates(self, dates: list[str]) -> None:
        if not dates:
            return
        parseable, skip_messages = self._split_parseable_dates(dates)
        if skip_messages:
            known = set(self._import_skip_messages)
            for message in skip_messages:
                if message not in known:
                    self._import_skip_messages.append(message)
                    known.add(message)
            self._sync_import_message()
        if not parseable:
            return
        self._start_worker(
            ParseLogsWorker(parseable),
            indeterminate=False,
            for_parse=True,
            on_start=lambda: self._mark_parsing_dates(parseable),
            on_progress=lambda current, total, text: self._set_progress(current, total, text, parse=True),
            on_ok=self._on_parse_batch_success,
        )

    def _on_parse_batch_success(self, result) -> None:
        saved: list[dict] = []
        failed: dict[str, str] = {}
        if result is not None:
            saved = list(getattr(result, "saved", []) or [])
            failed = dict(getattr(result, "failed", {}) or {})
        for date, reason in failed.items():
            self._failed_dates[date] = reason
        for item in saved:
            date = item.get("date")
            if date:
                self._failed_dates.pop(date, None)
        self.refresh_data()
        parsed_days = len({item.get("date") for item in saved if item.get("date")})
        if not self._import_skip_messages and not self._failed_dates:
            suffix = f"{parsed_days} day(s)" if parsed_days else "logs"
            self._set_import_message(f"Parsed {suffix}.", error=False)
        else:
            self._sync_import_message()

    def _mark_parsing_dates(self, dates: list[str]) -> None:
        self._parsing_dates = set(dates)
        for date in dates:
            self._failed_dates.pop(date, None)
        self._render_views()

    def _clear_parsing(self, *, success: bool) -> None:
        if not success:
            for date in self._parsing_dates:
                self._failed_dates[date] = self._last_worker_error or "Parse failed"
        else:
            for date in self._parsing_dates:
                self._failed_dates.pop(date, None)
        self._parsing_dates = set()
        self._render_views()
        if not success:
            self._sync_import_message()

    def _on_tab_changed(self, index: int) -> None:
        if index == 1 and not self.report_panel.date_from.text().strip():
            self._sync_report_dates(self._selected_dates)

    def _upload_logs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select ACS log files",
            "",
            "Log files (*.log);;All files (*.*)",
        )
        if not paths:
            return
        self._upload_paths(paths)

    def _upload_paths(self, paths: list[str]) -> None:
        if not paths:
            return
        self._import_skip_messages = []
        self.import_panel.clear_message()
        self._start_worker(
            UploadLogsWorker(paths),
            indeterminate=False,
            for_parse=True,
            on_progress=lambda current, total, name: self._set_progress(
                current, total, f"Uploading {name}", parse=True
            ),
            on_ok=self._after_upload,
        )

    def _after_upload(self, result) -> None:
        saved = list(getattr(result, "saved", []) or [])
        upload_errors = list(getattr(result, "errors", []) or [])
        self.refresh_data()
        uploaded_dates = {record["logDate"] for record in saved}
        if uploaded_dates:
            self._last_upload_date = max(uploaded_dates)
        for upload_date in uploaded_dates:
            self._failed_dates.pop(upload_date, None)
        ready_dates, reparse_days, skip_messages = self._upload_parse_plan(uploaded_dates)
        self._import_skip_messages = skip_messages + upload_errors
        if self._import_skip_messages:
            self._sync_import_message()
        parse_dates = list(ready_dates)
        if reparse_days and self._confirm_reparse(reparse_days):
            for item in reparse_days:
                delete_csv_day(item["date"])
                parse_dates.append(item["date"])
        elif reparse_days:
            self._set_import_message(
                "Upload complete. Re-parse cancelled — existing parsed data kept.",
                error=False,
            )
        if parse_dates:
            self._parse_dates(parse_dates)
        elif not self._import_skip_messages and not reparse_days:
            self._set_import_message("Upload complete.", error=False)
        if self._last_upload_date:
            self._select_day(self._last_upload_date)

    def _upload_parse_plan(
        self, uploaded_dates: set[str]
    ) -> tuple[list[str], list[dict], list[str]]:
        day_by_date = {day["date"]: day for day in self._coverage_days}
        ready_dates: list[str] = []
        reparse_days: list[dict] = []
        skip_messages: list[str] = []
        for date in sorted(uploaded_dates):
            day = day_by_date.get(date)
            if not day:
                continue
            log_day = day.get("log_day") or {}
            missing = _missing_acs_nodes(log_day)
            if missing:
                skip_messages.append(
                    f"{date}: missing {', '.join(missing)} log — parsing skipped"
                )
                continue
            csv_day = day.get("csv_day")
            if not csv_day:
                ready_dates.append(date)
                continue
            log_min, log_max = scan_log_datetime_range(date)
            if not log_max:
                skip_messages.append(f"{date}: uploaded logs have no timestamps — parsing skipped")
                continue
            csv_min = str(csv_day.get("minDateTime") or "")
            csv_max = str(csv_day.get("maxDateTime") or "")
            if log_max <= csv_max and (not csv_min or log_min >= csv_min):
                continue
            reparse_days.append(
                {
                    "date": date,
                    "csv_min": csv_min,
                    "csv_max": csv_max,
                    "log_min": log_min,
                    "log_max": log_max,
                }
            )
        return ready_dates, reparse_days, skip_messages

    def _confirm_reparse(self, reparse_days: list[dict]) -> bool:
        lines: list[str] = []
        for item in reparse_days:
            parsed_range = self._format_datetime_range(item["csv_min"], item["csv_max"])
            log_range = self._format_datetime_range(item["log_min"], item["log_max"])
            lines.append(
                f"{item['date']}\n"
                f"  Parsed: {parsed_range}\n"
                f"  New logs: {log_range}"
            )
        body = (
            "Uploaded logs extend beyond the existing parse.\n\n"
            + "\n\n".join(lines)
            + "\n\nDelete parsed CSV and re-parse these day(s)?"
        )
        reply = QMessageBox.question(
            self,
            "Re-parse day",
            body,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    @staticmethod
    def _format_datetime_range(min_value: str, max_value: str) -> str:
        if min_value and max_value:
            return f"{min_value} – {max_value}"
        if max_value:
            return f"until {max_value}"
        if min_value:
            return f"from {min_value}"
        return "—"

    def _sync_import_message(self) -> None:
        lines = list(self._import_skip_messages)
        lines.extend(f"{date}: {reason}" for date, reason in sorted(self._failed_dates.items()))
        if lines:
            self._set_import_message("\n".join(lines), error=True)
        else:
            self.import_panel.clear_message()

    def _set_import_message(self, text: str, *, error: bool = False) -> None:
        self.import_panel.set_message(text, error=error)

    def _delete_day(self, day_date: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete day data",
            f"Delete all logs and CSV for {day_date}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(
            DeleteDayWorker(day_date),
            indeterminate=True,
            for_parse=True,
            on_ok=lambda: self._on_day_deleted(day_date),
        )

    def _on_day_deleted(self, day_date: str) -> None:
        self._failed_dates.pop(day_date, None)
        if day_date in self._selected_dates:
            self._selected_dates = [date for date in self._selected_dates if date != day_date]
        if self._last_upload_date == day_date:
            self._last_upload_date = ""
        self.refresh_data()
        self._set_import_message(f"Deleted data for {day_date}.", error=False)

    def _report_kwargs(self, *, limit: int | None = None, offset: int | None = None) -> dict:
        panel = self.report_panel
        date_from, date_to = validate_report_range(
            panel.date_from.text(),
            panel.date_to.text(),
        )
        if panel.uses_custom_sql():
            mode = "custom"
        elif panel.uses_txn_filter():
            mode = "txnId"
        else:
            mode = "date"
        kwargs = {
            "mode": mode,
            "date_from": date_from,
            "date_to": date_to,
            "txn_id": panel.txn_id.text().strip() or None,
        }
        if mode == "custom":
            sql = panel.custom_sql()
            if "%(date_from)s" not in sql and "areq.messagedatetime >=" in sql.lower():
                sql = apply_literal_dates_to_sql(
                    sql,
                    date_from,
                    date_to,
                )
            kwargs["sql"] = sql
        if limit is not None:
            kwargs["limit"] = limit
        if offset is not None:
            kwargs["offset"] = offset
        return kwargs

    def _run_report(self) -> None:
        try:
            kwargs = self._report_kwargs(limit=CHUNK_SIZE, offset=0)
        except ValueError as error:
            QMessageBox.warning(self, "Report", str(error))
            return
        self._report_offset = 0
        self._report_rows = []
        self.report_panel.prepare_run()
        self._start_worker(
            ReportRunWorker(**kwargs),
            indeterminate=True,
            on_ok=self._on_report_page,
            status="Running report preview…",
        )

    def _load_more_report(self) -> None:
        if self._report_offset + CHUNK_SIZE >= self._report_total:
            return
        self._report_offset += CHUNK_SIZE
        self._start_worker(
            ReportRunWorker(**self._report_kwargs(limit=CHUNK_SIZE, offset=self._report_offset)),
            indeterminate=True,
            on_ok=self._append_report_page,
            status="Loading more rows…",
        )

    def _on_report_page(self, result) -> None:
        self._report_columns = result.columns
        self._report_rows = list(result.rows)
        self._report_total = result.row_count
        self.report_panel.render_table(self._report_columns, self._report_rows)
        shown = len(self._report_rows)
        self.report_panel.set_total_rows(self._report_total)
        self.report_panel.set_shown_rows(shown, self._report_total)
        self.report_panel.set_status(f"Preview: {shown:,} of {self._report_total:,} rows")
        self.report_panel.set_load_more_enabled(shown < self._report_total)
        self.report_panel.set_export_visible(True)
        self.report_panel.collapse_filters()

    def _append_report_page(self, result) -> None:
        self._report_rows.extend(result.rows)
        self.report_panel.render_table(self._report_columns, self._report_rows)
        shown = len(self._report_rows)
        self.report_panel.set_shown_rows(shown, self._report_total)
        self.report_panel.set_status(f"Preview: {shown:,} of {self._report_total:,} rows")
        self.report_panel.set_load_more_enabled(shown < self._report_total)

    def _export_report(self) -> None:
        try:
            kwargs = self._report_kwargs()
        except ValueError as error:
            QMessageBox.warning(self, "Report", str(error))
            return
        self._start_worker(
            ReportExportWorker(**kwargs),
            indeterminate=True,
            on_ok=self._on_export_done,
            status="Export: building report…",
        )

    def _on_export_done(self, result) -> None:
        path = Path(result.output_path)
        self._set_status(f"Exported {result.row_count:,} rows to {path.name}")
        QMessageBox.information(
            self,
            "Export complete",
            f"Saved {result.row_count:,} rows to Excel:\n{path}\n\nFolder:\n{get_report_output_dir()}",
        )

    def _start_worker(
        self,
        worker,
        *,
        indeterminate: bool,
        for_parse: bool = False,
        on_start=None,
        on_progress=None,
        on_ok=None,
        status: str = "",
    ) -> None:
        self._last_worker_error = ""
        if self._active_worker and self._active_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Another task is already running.")
            return
        self._active_worker = worker
        if for_parse:
            self.import_panel.set_busy(True)
            if indeterminate:
                self.import_panel.set_progress(visible=True, current=0, total=0)
            else:
                self.import_panel.set_progress(visible=True, current=0, total=100)
        else:
            self.report_panel.set_progress_visible(True)
            if indeterminate:
                self.report_panel.progress.setRange(0, 0)
            else:
                self.report_panel.progress.setRange(0, 100)
        if status:
            self._set_status(status, parse=for_parse)
        if on_start:
            on_start()
        if on_progress:
            worker.progress.connect(on_progress)
        worker.finished_ok.connect(lambda payload=None: self._worker_done(on_ok, payload, for_parse=for_parse))
        worker.failed.connect(lambda message: self._worker_failed(message, for_parse=for_parse))
        worker.start()

    def _worker_done(self, callback, payload, *, for_parse: bool = False) -> None:
        if for_parse:
            self.import_panel.set_progress(visible=False)
            self.import_panel.set_busy(False)
        else:
            self.report_panel.set_progress_visible(False)
            self.report_panel.progress.setRange(0, 100)
        self._active_worker = None
        if for_parse and self._parsing_dates:
            self._clear_parsing(success=True)
        if callback:
            callback(payload) if payload is not None else callback()

    def _worker_failed(self, message: str, *, for_parse: bool = False) -> None:
        self._last_worker_error = message
        if for_parse:
            self.import_panel.set_progress(visible=False)
            self.import_panel.set_busy(False)
        else:
            self.report_panel.set_progress_visible(False)
            self.report_panel.progress.setRange(0, 100)
            self.report_panel.set_status("")
            QMessageBox.critical(self, "Error", message)
        self._active_worker = None
        if for_parse and self._parsing_dates:
            self._clear_parsing(success=False)
        elif for_parse:
            self._set_import_message(message, error=True)

    def _set_progress(self, current: int, total: int, label: str, *, parse: bool = False) -> None:
        if parse:
            self.import_panel.set_progress(visible=True, current=current, total=total)
            return
        progress = self.report_panel.progress
        if total > 0:
            progress.setRange(0, total)
            progress.setValue(current)
        self._set_status(f"{label} ({current}/{total})" if total else label, parse=parse)

    def _set_status(self, text: str, *, parse: bool = False) -> None:
        if parse:
            return
        self.report_panel.set_status(text)
