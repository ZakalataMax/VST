from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from app.common.elastic_logs import iter_days, plan_download_dates
from app.common.report_utils import validate_report_range
from app.threeds.log_storage import elastic_download_complete, list_log_days, read_log_content
from app.threeds.paths import get_report_output_dir
from app.threeds.services.csv_storage import delete_csv_day, list_csv_days
from desktop.tools.threeds.coverage import build_coverage_days
from desktop.tools.threeds.report_sql_utils import apply_literal_dates_to_sql
from desktop.tools.threeds.widgets.coverage_sidebar import ThreeDsCoverageSidebar
from desktop.tools.threeds.widgets.download_panel import DownloadPanel
from desktop.tools.threeds.widgets.log_viewer import LogViewer
from desktop.tools.threeds.widgets.report_panel import ReportPanel
from desktop.tools.threeds.workers import (
    ThreeDsDeleteDayWorker,
    ThreeDsDownloadWorker,
    ThreeDsParseLogsWorker,
    ThreeDsReportExportWorker,
    ThreeDsReportRunWorker,
)

CHUNK_SIZE = 100


class ThreeDsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._coverage_days: list[dict] = []
        self._selected_dates: list[str] = []
        self._active_worker = None
        self._skipped_download_dates: list[str] = []
        self._parsing_dates: set[str] = set()
        self._failed_dates: dict[str, str] = {}
        self._report_columns: list[str] = []
        self._report_rows: list[dict] = []
        self._report_offset = 0
        self._report_total = 0
        self._last_worker_error = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = ThreeDsCoverageSidebar()
        self.sidebar.days_selected.connect(self._on_sidebar_days_selected)
        root.addWidget(self.sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.tabs = QTabWidget()

        self.download_panel = DownloadPanel()
        self.download_panel.download_requested.connect(self._download_from_elastic)
        self.download_panel.cancel_download_requested.connect(self._cancel_download)
        self.download_panel.delete_requested.connect(self._delete_day)
        self.download_panel.parse_requested.connect(self._reparse_day_requested)
        self.tabs.addTab(self.download_panel, "Import & Parse")

        self.log_viewer = LogViewer()
        self.tabs.addTab(self.log_viewer, "Raw Log")

        self.report_panel = ReportPanel()
        self.report_panel.run_requested.connect(self._run_report)
        self.report_panel.export_requested.connect(self._export_report)
        self.report_panel.load_more_requested.connect(self._load_more_report)
        self.tabs.addTab(self.report_panel, "Report")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        content_layout.addWidget(self.tabs, stretch=1)
        root.addWidget(content, stretch=1)

        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            log_days = list_log_days()
            csv_days = list_csv_days()
            self._coverage_days = build_coverage_days(
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
        days = [self._day_by_date(day_date) for day_date in self._selected_dates]
        days = [day for day in days if day]
        if not days and self._coverage_days:
            days = [self._coverage_days[0]]
        self._apply_days_selection(days)

    def _day_by_date(self, day_date: str) -> dict | None:
        return next((item for item in self._coverage_days if item["date"] == day_date), None)

    def _apply_days_selection(self, days: list[dict]) -> None:
        dates = [day["date"] for day in days]
        self._selected_dates = dates
        self.sidebar.set_selected_dates(dates)
        self.download_panel.set_days(days)
        self._update_log_viewer(dates)
        self._sync_report_dates(dates)

    def _sync_report_dates(self, dates: list[str]) -> None:
        if not dates:
            return
        sorted_dates = sorted(dates)
        self.report_panel.set_date_range(sorted_dates[0], sorted_dates[-1])

    def _on_tab_changed(self, index: int) -> None:
        if index == 2 and not self.report_panel.date_from.text().strip():
            self._sync_report_dates(self._selected_dates)

    def _update_log_viewer(self, dates: list[str]) -> None:
        if len(dates) != 1:
            hint = (
                "Select exactly one downloaded day to view its raw log."
                if not dates
                else "Select a single day (not multiple) to view its raw log."
            )
            self.log_viewer.show_hint(hint)
            return
        try:
            content = read_log_content(dates[0])
        except ValueError as error:
            self.log_viewer.show_hint(str(error))
            return
        self.log_viewer.show_content(dates[0], content)

    def _select_days(self, dates: list[str]) -> None:
        days = [self._day_by_date(day_date) for day_date in dates]
        days = [day for day in days if day]
        self._apply_days_selection(days)

    def _on_sidebar_days_selected(self, dates: list[str]) -> None:
        self._select_days(dates)

    def _download_from_elastic(self, date_from: str, date_to: str) -> None:
        if not date_from or not date_to:
            return
        if not os.getenv("ELASTIC_PASS"):
            QMessageBox.warning(
                self,
                "Elastic password required",
                "ELASTIC_PASS is not set.\n\n"
                "Add it to a .env file (copy .env.example to .env next to the app "
                "and fill in ELASTIC_PASS), or set the ELASTIC_PASS environment "
                "variable, then restart the app and try again.",
            )
            return
        today = date.today().isoformat()
        complete_days = {
            day for day in iter_days(date_from, date_to) if elastic_download_complete(day)
        }
        to_download, skipped, _future = plan_download_dates(
            date_from, date_to, today=today, downloaded=complete_days
        )
        self._skipped_download_dates = skipped
        if not to_download:
            if skipped:
                self._select_days([skipped[-1]])
                self.download_panel.set_message(
                    f"Already downloaded (full days) — skipped {len(skipped)} day(s): "
                    f"{', '.join(skipped)}.",
                    error=False,
                )
            else:
                self.download_panel.set_message(
                    "Nothing to download for the selected range.", error=False
                )
            return
        self.download_panel.clear_message()
        worker = ThreeDsDownloadWorker(to_download)
        self._active_worker = worker
        self.download_panel.set_busy(True)
        self.download_panel.begin_progress("Downloading from Elastic")
        worker.day_progress.connect(
            lambda index, count, day_date, percent: self.download_panel.update_progress(
                f"Downloading {day_date} ({index}/{count}) — {percent}%", percent
            )
        )
        worker.day_saved.connect(
            lambda day_date, rows: self.download_panel.add_progress_item(
                f"{day_date} — {rows:,} rows downloaded"
            )
        )
        worker.finished_ok.connect(self._after_elastic_download)
        worker.failed.connect(self._on_download_failed)
        worker.start()

    def _cancel_download(self) -> None:
        worker = self._active_worker
        if worker is None or not hasattr(worker, "request_cancel"):
            return
        worker.request_cancel()
        self.download_panel.set_cancel_download_enabled(False)
        self.download_panel.update_progress("Stopping download…", self.download_panel.progress.value())

    def _after_elastic_download(self, result) -> None:
        self.download_panel.end_progress()
        self.download_panel.set_busy(False)
        self._active_worker = None
        saved = list(getattr(result, "saved", []) or [])
        errors = list(getattr(result, "errors", []) or [])
        warnings = list(getattr(result, "warnings", []) or [])
        messages = errors + warnings
        self.refresh_data()
        downloaded_dates = {record["logDate"] for record in saved}
        if downloaded_dates:
            self._select_days(sorted(downloaded_dates))
        if messages:
            self.download_panel.set_message("\n".join(messages), error=bool(errors))
        elif getattr(result, "cancelled", False):
            self.download_panel.set_message(
                f"Download stopped. Saved {len(downloaded_dates)} day(s) before cancel.",
                error=False,
            )
        else:
            skip_note = (
                f" Skipped {len(self._skipped_download_dates)} fully downloaded day(s)."
                if self._skipped_download_dates
                else ""
            )
            self.download_panel.set_message(f"Download complete.{skip_note}", error=False)
        if downloaded_dates:
            self._parse_dates(sorted(downloaded_dates))

    def _on_download_failed(self, message: str) -> None:
        self.download_panel.end_progress()
        self.download_panel.set_busy(False)
        self._active_worker = None
        self.download_panel.set_message(message, error=True)

    def _delete_day(self, day_date: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete day data",
            f"Delete all logs and parsed CSV for {day_date}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        worker = ThreeDsDeleteDayWorker(day_date)
        self._active_worker = worker
        worker.finished_ok.connect(lambda: self._on_day_deleted(day_date))
        worker.failed.connect(lambda message: QMessageBox.critical(self, "Error", message))
        worker.start()

    def _on_day_deleted(self, day_date: str) -> None:
        self._active_worker = None
        self._failed_dates.pop(day_date, None)
        if day_date in self._selected_dates:
            self._selected_dates = [d for d in self._selected_dates if d != day_date]
        self.refresh_data()
        self.download_panel.set_message(f"Deleted data for {day_date}.", error=False)

    def _reparse_day_requested(self, day_date: str) -> None:
        if not day_date:
            return
        self.download_panel.clear_message()
        day = self._day_by_date(day_date)
        has_csv = bool(day and day.get("csv_day"))
        if has_csv:
            if not self._confirm_reparse(day_date):
                return
            delete_csv_day(day_date)
        self._parse_dates([day_date])

    def _confirm_reparse(self, day_date: str) -> bool:
        reply = QMessageBox.question(
            self,
            "Re-parse day",
            f"Parsed data already exists for {day_date}.\n\n"
            "Re-parsing replaces the existing parsed CSV with a fresh parse "
            "of the stored raw log.\n\n"
            "Delete the existing parsed CSV and re-parse?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _parse_dates(self, dates: list[str]) -> None:
        if not dates:
            return
        self._parsing_dates = set(dates)
        for day_date in dates:
            self._failed_dates.pop(day_date, None)
        self._render_views()
        worker = ThreeDsParseLogsWorker(dates)
        self._active_worker = worker
        self.download_panel.set_busy(True)
        self.download_panel.begin_progress("Parsing logs")
        worker.day_progress.connect(
            lambda index, total, day_date, percent: self.download_panel.update_progress(
                f"Parsing {day_date} ({index}/{total})", percent
            )
        )
        worker.day_done.connect(
            lambda day_date: self.download_panel.add_progress_item(f"{day_date} — parsed")
        )
        worker.finished_ok.connect(self._on_parse_batch_success)
        worker.failed.connect(self._on_parse_failed)
        worker.start()

    def _on_parse_batch_success(self, result) -> None:
        self.download_panel.end_progress()
        self.download_panel.set_busy(False)
        self._active_worker = None
        saved: list[dict] = []
        failed: dict[str, str] = {}
        warnings: list[str] = []
        if result is not None:
            saved = list(getattr(result, "saved", []) or [])
            failed = dict(getattr(result, "failed", {}) or {})
            warnings = list(getattr(result, "warnings", []) or [])
        for day_date, reason in failed.items():
            self._failed_dates[day_date] = reason
        for day_date in self._parsing_dates:
            if day_date not in failed:
                self._failed_dates.pop(day_date, None)
        self._parsing_dates = set()
        self.refresh_data()
        parsed_days = len({item.get("date") for item in saved if item.get("date")})
        if not failed and not warnings:
            suffix = f"{parsed_days} day(s)" if parsed_days else "logs"
            self.download_panel.set_message(f"Parsed {suffix}.", error=False)
        else:
            lines = list(warnings)
            lines.extend(f"{d}: {reason}" for d, reason in sorted(failed.items()))
            self.download_panel.set_message("\n".join(lines), error=bool(failed))

    def _on_parse_failed(self, message: str) -> None:
        self.download_panel.end_progress()
        self.download_panel.set_busy(False)
        self._active_worker = None
        for day_date in self._parsing_dates:
            self._failed_dates[day_date] = message
        self._parsing_dates = set()
        self.refresh_data()
        self.download_panel.set_message(message, error=True)

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
                sql = apply_literal_dates_to_sql(sql, date_from, date_to)
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
        self.report_panel.set_progress_visible(True)
        worker = ThreeDsReportRunWorker(**kwargs)
        self._active_worker = worker
        worker.finished_ok.connect(self._on_report_page)
        worker.failed.connect(self._on_report_failed)
        worker.start()

    def _load_more_report(self) -> None:
        if self._report_offset + CHUNK_SIZE >= self._report_total:
            return
        self._report_offset += CHUNK_SIZE
        worker = ThreeDsReportRunWorker(**self._report_kwargs(limit=CHUNK_SIZE, offset=self._report_offset))
        self._active_worker = worker
        self.report_panel.set_progress_visible(True)
        worker.finished_ok.connect(self._append_report_page)
        worker.failed.connect(self._on_report_failed)
        worker.start()

    def _on_report_page(self, result) -> None:
        self.report_panel.set_progress_visible(False)
        self._active_worker = None
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

    def _append_report_page(self, result) -> None:
        self.report_panel.set_progress_visible(False)
        self._active_worker = None
        self._report_rows.extend(result.rows)
        self.report_panel.render_table(self._report_columns, self._report_rows)
        shown = len(self._report_rows)
        self.report_panel.set_shown_rows(shown, self._report_total)
        self.report_panel.set_status(f"Preview: {shown:,} of {self._report_total:,} rows")
        self.report_panel.set_load_more_enabled(shown < self._report_total)

    def _on_report_failed(self, message: str) -> None:
        self.report_panel.set_progress_visible(False)
        self._active_worker = None
        self.report_panel.set_status("")
        QMessageBox.critical(self, "Error", message)

    def _export_report(self) -> None:
        try:
            kwargs = self._report_kwargs()
        except ValueError as error:
            QMessageBox.warning(self, "Report", str(error))
            return
        worker = ThreeDsReportExportWorker(
            **kwargs,
            native_pivot=self.report_panel.native_pivot_enabled(),
        )
        self._active_worker = worker
        self.report_panel.set_progress_visible(True)
        self.report_panel.set_status("Export: building report…")
        worker.finished_ok.connect(self._on_export_done)
        worker.failed.connect(self._on_export_failed)
        worker.start()

    def _on_export_done(self, result) -> None:
        self.report_panel.set_progress_visible(False)
        self._active_worker = None
        path = Path(result.output_path)
        self.report_panel.set_status(f"Exported {result.row_count:,} rows to {path.name}")
        pivot_added = getattr(result, "pivot_added", False)
        pivot_error = getattr(result, "pivot_error", "")
        if pivot_error and pivot_added:
            pivot_note = f"\n\nPivot: {pivot_error}"
        elif pivot_error:
            pivot_note = (
                "\n\nPivot sheet was NOT created (Data and Summary sheets are still "
                f"available):\n{pivot_error}"
            )
        else:
            pivot_note = ""
        QMessageBox.information(
            self,
            "Export complete",
            f"Saved {result.row_count:,} rows to Excel:\n{path}\n\n"
            f"Folder:\n{get_report_output_dir()}{pivot_note}",
        )

    def _on_export_failed(self, message: str) -> None:
        self.report_panel.set_progress_visible(False)
        self._active_worker = None
        self.report_panel.set_status("")
        QMessageBox.critical(self, "Error", message)
