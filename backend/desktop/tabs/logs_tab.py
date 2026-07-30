from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.paths import get_report_output_dir
from app.services.elastic_logs import iter_days, plan_download_dates
from app.services.report import validate_report_range
from app.services.csv_storage import list_csv_days
from app.services.csv_storage import delete_csv_day
from app.services.log_storage import (
    elastic_download_complete,
    has_elastic_log,
    list_log_days,
    list_log_files,
)
from desktop.coverage_utils import (
    build_coverage_days,
    day_has_logs,
)
from desktop.report_sql_utils import apply_literal_dates_to_sql
from desktop.widgets.coverage_sidebar import CoverageSidebar
from desktop.widgets.import_parse_panel import ImportParsePanel
from desktop.widgets.report_panel import ReportPanel
from desktop.workers import (
    DeleteDayWorker,
    ElasticDownloadLogsWorker,
    ParseLogsWorker,
    ReportExportWorker,
    ReportRunWorker,
)

CHUNK_SIZE = 100


def _format_range_for_email(date_from: str, date_to: str) -> str:
    def fmt(value: str) -> str:
        parsed = datetime.strptime(value.split(".", 1)[0], "%Y-%m-%d %H:%M:%S")
        return parsed.strftime("%d.%m.%Y %H:%M:%S")

    return f"{fmt(date_from)} - {fmt(date_to)}"


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
        self._skipped_download_dates: list[str] = []
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
        self.import_panel.download_requested.connect(self._download_from_elastic)
        self.import_panel.cancel_download_requested.connect(self._cancel_download)
        self.import_panel.parse_requested.connect(self._reparse_day_requested)
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

    def _split_parseable_dates(self, dates: list[str]) -> tuple[list[str], list[str]]:
        day_by_date = {day["date"]: day for day in self._coverage_days}
        parseable: list[str] = []
        skip_messages: list[str] = []
        for date in sorted(dates):
            day = day_by_date.get(date)
            if not day:
                continue
            log_day = day.get("log_day") or {}
            if not day_has_logs(log_day):
                skip_messages.append(
                    f"{date}: no logs downloaded — parsing skipped"
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
            progress_phase="parse",
            on_start=lambda: self._mark_parsing_dates(parseable),
            on_day_progress=lambda index, total, day, percent: self.import_panel.update_progress(
                f"Parsing {day} ({index}/{total})", percent, phase="parse"
            ),
            on_day_done=lambda day: self.import_panel.add_progress_item(f"{day} — parsed"),
            on_ok=self._on_parse_batch_success,
            status="Parsing logs",
        )

    def _on_parse_batch_success(self, result) -> None:
        saved: list[dict] = []
        failed: dict[str, str] = {}
        warnings: list[str] = []
        if result is not None:
            saved = list(getattr(result, "saved", []) or [])
            failed = dict(getattr(result, "failed", {}) or {})
            warnings = list(getattr(result, "warnings", []) or [])
        for date, reason in failed.items():
            self._failed_dates[date] = reason
        for message in warnings:
            if message not in self._import_skip_messages:
                self._import_skip_messages.append(message)
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
            day
            for day in iter_days(date_from, date_to)
            if elastic_download_complete(day)
        }
        to_download, skipped, _future = plan_download_dates(
            date_from,
            date_to,
            today=today,
            downloaded=complete_days,
        )
        self._skipped_download_dates = skipped
        if not to_download:
            if skipped:
                self._select_day(skipped[-1])
                self._set_import_message(
                    f"Already downloaded (full days) — skipped {len(skipped)} day(s): "
                    f"{self._format_dates(skipped)}.",
                    error=False,
                )
            else:
                self._set_import_message(
                    "Nothing to download for the selected range.",
                    error=False,
                )
            return
        self._import_skip_messages = []
        self.import_panel.clear_message()
        self._start_worker(
            ElasticDownloadLogsWorker(to_download),
            indeterminate=False,
            for_parse=True,
            progress_phase="download",
            on_day_progress=lambda index, count, day, percent: self.import_panel.update_progress(
                f"Downloading {day} ({index}/{count}) — {percent}%", percent, phase="download"
            ),
            on_day_saved=self._on_day_downloaded,
            on_ok=self._after_elastic_download,
            status="Downloading from Elastic",
        )

    def _on_day_downloaded(self, day_date: str, rows: int) -> None:
        self.import_panel.add_progress_item(f"{day_date} — {rows:,} rows downloaded")
        self.refresh_data()

    def _after_elastic_download(self, result) -> None:
        saved = list(getattr(result, "saved", []) or [])
        errors = list(getattr(result, "errors", []) or [])
        warnings = list(getattr(result, "warnings", []) or [])
        errors = errors + warnings
        self.refresh_data()
        downloaded_dates = {record["logDate"] for record in saved}
        if downloaded_dates:
            self._last_upload_date = max(downloaded_dates)
        for download_date in downloaded_dates:
            self._failed_dates.pop(download_date, None)
        self._import_skip_messages = errors
        if errors:
            self._sync_import_message()
        if self._last_upload_date:
            self._select_day(self._last_upload_date)
        skipped = getattr(self, "_skipped_download_dates", [])
        skip_note = (
            f" Skipped {len(skipped)} fully downloaded day(s)."
            if skipped
            else ""
        )
        if downloaded_dates:
            if getattr(result, "cancelled", False):
                self._set_import_message(
                    f"Download stopped. Saved {len(downloaded_dates)} day(s) before cancel.{skip_note}",
                    error=False,
                )
            self._parse_after_download(sorted(downloaded_dates), skip_note=skip_note)
        elif getattr(result, "cancelled", False):
            self._set_import_message("Download stopped.", error=False)
        elif not errors:
            self._set_import_message(f"Download complete.{skip_note}", error=False)

    def _parse_after_download(self, dates: list[str], *, skip_note: str = "") -> None:
        csv_dates = {day["date"] for day in self._coverage_days if day.get("csv_day")}
        parse_dates: list[str] = []
        for download_date in dates:
            if download_date in csv_dates:
                delete_csv_day(download_date)
            parse_dates.append(download_date)
        if parse_dates:
            self._parse_dates(parse_dates)

    def _reparse_day_requested(self, log_date: str) -> None:
        if not log_date:
            return
        self._import_skip_messages = []
        self.import_panel.clear_message()
        day = self._day_by_date(log_date)
        has_csv = bool(day and day.get("csv_day"))
        if has_csv:
            if not self._confirm_reparse([log_date]):
                return
            delete_csv_day(log_date)
        self._parse_dates([log_date])

    def _confirm_reparse(self, reparse_days: list[str]) -> bool:
        days_text = ", ".join(reparse_days)
        body = (
            f"Parsed data already exists for {days_text}.\n\n"
            "Re-parsing replaces the existing parsed CSV with a fresh parse "
            "of the stored raw logs.\n\n"
            "Delete the existing parsed CSV and re-parse?"
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
    def _format_dates(dates: list[str], *, limit: int = 5) -> str:
        if len(dates) <= limit:
            return ", ".join(dates)
        head = ", ".join(dates[:limit])
        return f"{head} (+{len(dates) - limit} more)"

    def _sync_import_message(self) -> None:
        lines = list(self._import_skip_messages)
        lines.extend(f"{date}: {reason}" for date, reason in sorted(self._failed_dates.items()))
        if lines:
            self._set_import_message("\n".join(lines), error=True)
        else:
            self.import_panel.clear_message()

    def _set_import_message(self, text: str, *, error: bool = False) -> None:
        self.import_panel.set_message(text, error=error)

    def _cancel_download(self) -> None:
        worker = self._active_worker
        if worker is None or not hasattr(worker, "request_cancel"):
            return
        worker.request_cancel()
        self.import_panel.set_cancel_download_enabled(False)
        self.import_panel.update_progress("Stopping download…", self.import_panel.progress.value())

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
        email_recipients = None
        email_body = None
        if self.report_panel.email_enabled():
            date_range_text = _format_range_for_email(kwargs["date_from"], kwargs["date_to"])
            composed = self.report_panel.compose_email(
                default_body=f"ACS Approval Rate report\n\n{date_range_text}\n\nReport attached.",
                date_range_text=date_range_text,
            )
            if composed is None:
                return
            email_recipients, email_body = composed
            if not email_recipients:
                QMessageBox.warning(
                    self,
                    "Report",
                    "Enter at least one recipient email, or uncheck Email report.",
                )
                return
        self._start_worker(
            ReportExportWorker(
                **kwargs,
                native_pivot=self.report_panel.native_pivot_enabled(),
                email_recipients=email_recipients,
                email_body=email_body,
            ),
            indeterminate=True,
            on_ok=self._on_export_done,
            status="Export: building report…",
        )

    def _on_export_done(self, result) -> None:
        path = Path(result.output_path)
        self._set_status(f"Exported {result.row_count:,} rows to {path.name}")
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
        email_status = getattr(result, "email_status", "")
        email_note = f"\n\nEmail: {email_status}" if email_status else ""
        QMessageBox.information(
            self,
            "Export complete",
            f"Saved {result.row_count:,} rows to Excel:\n{path}\n\n"
            f"Folder:\n{get_report_output_dir()}{pivot_note}{email_note}",
        )

    def _start_worker(
        self,
        worker,
        *,
        indeterminate: bool,
        for_parse: bool = False,
        progress_phase: str = "",
        on_start=None,
        on_progress=None,
        on_day_progress=None,
        on_day_saved=None,
        on_day_done=None,
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
            self.import_panel.begin_progress(
                status or "Working…",
                indeterminate=indeterminate,
                phase=progress_phase,
            )
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
        if on_day_progress and hasattr(worker, "day_progress"):
            worker.day_progress.connect(on_day_progress)
        if on_day_saved and hasattr(worker, "day_saved"):
            worker.day_saved.connect(on_day_saved)
        if on_day_done and hasattr(worker, "day_done"):
            worker.day_done.connect(on_day_done)
        worker.finished_ok.connect(lambda payload=None: self._worker_done(on_ok, payload, for_parse=for_parse))
        worker.failed.connect(lambda message: self._worker_failed(message, for_parse=for_parse))
        worker.start()

    def _worker_done(self, callback, payload, *, for_parse: bool = False) -> None:
        if for_parse:
            self.import_panel.end_progress()
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
            self.import_panel.end_progress()
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

    def _set_status(self, text: str, *, parse: bool = False) -> None:
        if parse:
            return
        self.report_panel.set_status(text)
