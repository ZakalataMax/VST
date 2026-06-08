from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.paths import get_report_output_dir
from app.services.csv_storage import list_csv_days
from app.services.log_storage import list_log_days, list_log_files
from desktop.coverage_utils import build_coverage_days, detect_acs_node
from desktop.report_sql_utils import apply_literal_dates_to_sql, load_report_template_sql
from desktop.widgets.common import Card, SectionHeader, field_label, ghost_button, primary_button, secondary_button
from desktop.widgets.coverage_sidebar import CoverageSidebar
from desktop.widgets.day_action_row import DayActionRow
from desktop.workers import ParseLogsWorker, ReportExportWorker, ReportRunWorker, UploadLogsWorker

CHUNK_SIZE = 100


def _validate_queue_pairs(file_ids: list[str], files: list[dict]) -> str:
    by_id = {item["id"]: item for item in files}
    by_date: dict[str, set[str]] = {}
    for file_id in file_ids:
        item = by_id.get(file_id)
        if not item:
            return f"Unknown file id: {file_id}"
        node = item.get("acsNode") or detect_acs_node(item.get("filename", ""))
        if not node:
            return f"Log file name must include ACS1 or ACS2: {item.get('filename')}"
        log_date = item.get("logDate")
        if not log_date:
            return f"Missing log date for: {item.get('filename')}"
        by_date.setdefault(log_date, set()).add(node)

    missing = sorted(
        date for date, nodes in by_date.items() if not ("acs1" in nodes and "acs2" in nodes)
    )
    if missing:
        return f"Each date must include both ACS1 and ACS2 logs. Missing pair for: {', '.join(missing)}"
    return ""


class CellDetailDialog(QDialog):
    def __init__(self, title: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        header = QLabel(title)
        header.setObjectName("CardTitle")
        layout.addWidget(header)
        editor = QPlainTextEdit(value or "—")
        editor.setReadOnly(True)
        editor.setMinimumHeight(360)
        layout.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class LogsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._files: list[dict] = []
        self._coverage_days: list[dict] = []
        self._queue_ids: list[str] = []
        self._day_rows: list[DayActionRow] = []
        self._report_columns: list[str] = []
        self._report_rows: list[dict] = []
        self._report_offset = 0
        self._report_total = 0
        self._active_worker = None

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = CoverageSidebar()
        self.sidebar.day_selected.connect(self._on_coverage_selected)
        root.addWidget(self.sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 16)
        content_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_parse_tab(), "Import & Parse")
        self.tabs.addTab(self._build_report_tab(), "Report")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        content_layout.addWidget(self.tabs)
        root.addWidget(content, stretch=1)

        self.refresh_data()

    def _build_parse_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        card = Card()
        header_row = QHBoxLayout()
        header_row.addWidget(SectionHeader("Log days"))
        header_row.addStretch()
        upload_btn = primary_button("Upload logs…")
        upload_btn.clicked.connect(self._upload_logs)
        refresh_btn = secondary_button("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        header_row.addWidget(upload_btn)
        header_row.addWidget(refresh_btn)
        card.add_layout(header_row)

        self.parse_status = QLabel("Upload ACS1 and ACS2 .log files, then click Parse on a day.")
        self.parse_status.setObjectName("MutedLabel")
        self.parse_status.setWordWrap(True)
        card.add_widget(self.parse_status)

        self.parse_progress = QProgressBar()
        self.parse_progress.setVisible(False)
        self.parse_progress.setFixedHeight(6)
        card.add_widget(self.parse_progress)

        self.days_scroll = QScrollArea()
        self.days_scroll.setWidgetResizable(True)
        self.days_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.days_body = QWidget()
        self.days_layout = QVBoxLayout(self.days_body)
        self.days_layout.setContentsMargins(0, 0, 0, 0)
        self.days_layout.setSpacing(8)
        self.days_layout.addStretch()
        self.days_scroll.setWidget(self.days_body)
        self.days_scroll.setMinimumHeight(220)
        card.add_widget(self.days_scroll)

        queue_header = QHBoxLayout()
        self.queue_header = SectionHeader("Batch queue")
        queue_header.addWidget(self.queue_header)
        queue_header.addStretch()
        clear_queue_btn = ghost_button("Clear")
        clear_queue_btn.clicked.connect(self._clear_queue)
        parse_queue_btn = primary_button("Parse queue")
        parse_queue_btn.clicked.connect(self._parse_queue)
        queue_header.addWidget(clear_queue_btn)
        queue_header.addWidget(parse_queue_btn)
        card.add_layout(queue_header)

        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(96)
        card.add_widget(self.queue_list)
        layout.addWidget(card)
        return tab

    def _build_report_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        card = Card()
        self.report_header = SectionHeader("Report")
        card.add_widget(self.report_header)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        from_col = QVBoxLayout()
        from_col.setSpacing(6)
        from_col.addWidget(field_label("From"))
        self.date_from = QLineEdit()
        self.date_from.setPlaceholderText("2026-05-27")
        self.date_from.textChanged.connect(lambda: self._apply_dates_to_sql())
        from_col.addWidget(self.date_from)
        filters.addLayout(from_col)

        to_col = QVBoxLayout()
        to_col.setSpacing(6)
        to_col.addWidget(field_label("To"))
        self.date_to = QLineEdit()
        self.date_to.setPlaceholderText("2026-05-29")
        self.date_to.textChanged.connect(lambda: self._apply_dates_to_sql())
        to_col.addWidget(self.date_to)
        filters.addLayout(to_col)

        txn_col = QVBoxLayout()
        txn_col.setSpacing(6)
        txn_col.addWidget(field_label("Transaction ID"))
        self.txn_id = QLineEdit()
        txn_col.addWidget(self.txn_id)
        filters.addLayout(txn_col, stretch=1)
        card.add_layout(filters)

        options = QHBoxLayout()
        self.custom_sql_check = QCheckBox("Custom SQL")
        self.custom_sql_check.toggled.connect(self._on_custom_sql_toggled)
        self.use_txn_id_check = QCheckBox("Filter by transaction ID")
        options.addWidget(self.custom_sql_check)
        options.addWidget(self.use_txn_id_check)
        options.addStretch()
        card.add_layout(options)

        self.sql_editor = QPlainTextEdit()
        self.sql_editor.setPlaceholderText("Custom SQL (SELECT or WITH …)")
        self.sql_editor.setVisible(False)
        self.sql_editor.setMinimumHeight(120)
        self.sql_editor.setMaximumHeight(180)
        card.add_widget(self.sql_editor)

        report_buttons = QHBoxLayout()
        run_btn = primary_button("Run preview")
        run_btn.clicked.connect(self._run_report)
        export_btn = secondary_button("Export CSV")
        export_btn.clicked.connect(self._export_report)
        self.load_more_btn = secondary_button("Load more")
        self.load_more_btn.clicked.connect(self._load_more_report)
        report_buttons.addWidget(run_btn)
        report_buttons.addWidget(export_btn)
        report_buttons.addWidget(self.load_more_btn)
        report_buttons.addStretch()
        card.add_layout(report_buttons)

        self.report_status = QLabel("")
        self.report_status.setObjectName("MutedLabel")
        card.add_widget(self.report_status)

        self.report_progress = QProgressBar()
        self.report_progress.setVisible(False)
        self.report_progress.setFixedHeight(6)
        card.add_widget(self.report_progress)

        self.report_table = QTableWidget()
        self.report_table.setAlternatingRowColors(True)
        self.report_table.setShowGrid(False)
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.report_table.cellDoubleClicked.connect(self._open_cell_detail)
        card.add_widget(self.report_table)
        layout.addWidget(card)
        return tab

    def refresh_data(self) -> None:
        try:
            self._files = list_log_files()
            log_days = list_log_days()
            csv_days = list_csv_days()
            self._coverage_days = build_coverage_days(self._files, log_days, csv_days)
            self._render_coverage()
            self._render_day_rows()
        except Exception as error:
            QMessageBox.critical(self, "Refresh failed", str(error))

    def _coverage_summary(self) -> str:
        with_pair = complete = total_rows = 0
        for day in self._coverage_days:
            log_day = day.get("log_day") or {}
            csv_day = day.get("csv_day")
            if log_day.get("acs1") and log_day.get("acs2"):
                with_pair += 1
            if day.get("complete"):
                complete += 1
            if csv_day:
                total_rows += int(csv_day.get("rowCount") or 0)
        return (
            f"{len(self._coverage_days)} days · {with_pair} pairs · "
            f"{complete} complete · {total_rows:,} rows"
        )

    def _render_coverage(self) -> None:
        self.sidebar.set_days(self._coverage_days, self._coverage_summary())

    def _saved_day_file_ids(self, day: dict) -> list[str]:
        day_files = day.get("files") or []
        if day_files:
            return [file["id"] for file in day_files if file.get("id")]
        log_day = day.get("log_day") or {}
        file_ids: list[str] = []
        for node in ("acs1", "acs2"):
            if log_day.get(node):
                file_ids.append(f"{day['date']}/{node}")
        return file_ids

    def _queued_dates(self) -> set[str]:
        dates: set[str] = set()
        for index in range(self.queue_list.count()):
            item = self.queue_list.item(index)
            if not item:
                continue
            file_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(file_id, str) and "/" in file_id:
                dates.add(file_id.split("/", 1)[0])
        return dates

    def _render_day_rows(self) -> None:
        while self.days_layout.count() > 1:
            item = self.days_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._day_rows = []

        saved_days = [day for day in self._coverage_days if self._saved_day_file_ids(day)]
        queued_dates = self._queued_dates()

        if not saved_days:
            empty = QLabel("No saved logs yet. Click Upload logs and select ACS1 + ACS2 files for the same date.")
            empty.setObjectName("MutedLabel")
            empty.setWordWrap(True)
            empty.setContentsMargins(4, 12, 4, 12)
            self.days_layout.insertWidget(0, empty)
            self._update_queue_header()
            return

        for day in saved_days:
            row = DayActionRow(day, in_queue=day["date"] in queued_dates)
            row.queue_clicked.connect(self._queue_day)
            row.parse_clicked.connect(self._parse_day)
            self.days_layout.insertWidget(self.days_layout.count() - 1, row)
            self._day_rows.append(row)
        self._update_queue_header()

    def _update_queue_header(self) -> None:
        count = self.queue_list.count()
        self.queue_header.set_badge(str(count) if count else "")

    def _day_label(self, day: dict) -> str:
        return day["date"]

    def _queue_day(self, day: dict) -> None:
        file_ids = self._saved_day_file_ids(day)
        if not file_ids:
            return
        self._add_file_ids_to_queue(file_ids, self._day_label(day))
        self._render_day_rows()

    def _parse_day(self, day: dict) -> None:
        file_ids = self._saved_day_file_ids(day)
        if not file_ids:
            return
        error = _validate_queue_pairs(file_ids, self._files)
        if error:
            QMessageBox.warning(self, "Parse", error)
            return
        self._start_worker(
            ParseLogsWorker(file_ids),
            indeterminate=True,
            for_parse=True,
            on_progress=lambda current, total, label: self._set_progress(current, total, label, parse=True),
            on_ok=lambda saved: (
                self.refresh_data(),
                self._set_status(f"Parsed {day['date']} ({len(saved)} day(s)).", parse=True),
            ),
        )

    def _on_coverage_selected(self, date: str) -> None:
        self.sidebar.set_selected_date(date)
        self.date_from.setText(date)
        self.date_to.setText(date)
        self.tabs.setCurrentIndex(1)
        if self.custom_sql_check.isChecked():
            self._apply_dates_to_sql()

    def _on_tab_changed(self, index: int) -> None:
        if index == 1 and not self.date_from.text().strip() and self._coverage_days:
            date = self._coverage_days[0]["date"]
            self.date_from.setText(date)
            self.date_to.setText(date)

    def _upload_logs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select ACS log files",
            "",
            "Log files (*.log);;All files (*.*)",
        )
        if not paths:
            return
        self._start_worker(
            UploadLogsWorker(paths),
            indeterminate=False,
            for_parse=True,
            on_progress=lambda current, total, name: self._set_progress(
                current, total, f"Uploading {name}", parse=True
            ),
            on_ok=lambda: (self.refresh_data(), self._set_status("Upload complete.", parse=True)),
        )

    def _add_file_ids_to_queue(self, file_ids: list[str], label: str) -> None:
        existing = {self.queue_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queue_list.count())}
        for file_id in file_ids:
            if file_id in existing:
                continue
            self.queue_list.addItem(QListWidgetItem(f"{label} · {file_id.split('/')[-1].upper()}"))
            self.queue_list.item(self.queue_list.count() - 1).setData(Qt.ItemDataRole.UserRole, file_id)
            existing.add(file_id)
        self._queue_ids = [
            self.queue_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queue_list.count())
        ]
        self._update_queue_header()

    def _clear_queue(self) -> None:
        self.queue_list.clear()
        self._queue_ids = []
        self._update_queue_header()
        self._render_day_rows()

    def _parse_queue(self) -> None:
        self._queue_ids = [
            self.queue_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queue_list.count())
        ]
        if not self._queue_ids:
            QMessageBox.warning(self, "Parse", "Queue is empty. Click Queue on a day or Parse to run one day.")
            return
        error = _validate_queue_pairs(self._queue_ids, self._files)
        if error:
            QMessageBox.warning(self, "Parse", error)
            return
        self._start_worker(
            ParseLogsWorker(self._queue_ids),
            indeterminate=True,
            for_parse=True,
            on_progress=lambda current, total, label: self._set_progress(current, total, label, parse=True),
            on_ok=lambda saved: (
                self.refresh_data(),
                self._clear_queue(),
                self._set_status(f"Parsed {len(saved)} day(s).", parse=True),
            ),
        )

    def _on_custom_sql_toggled(self, checked: bool) -> None:
        self.sql_editor.setVisible(checked)
        if checked and not self.sql_editor.toPlainText().strip():
            self.sql_editor.setPlainText(load_report_template_sql())
        self._apply_dates_to_sql()

    def _apply_dates_to_sql(self) -> None:
        if not self.custom_sql_check.isChecked():
            return
        sql = self.sql_editor.toPlainText()
        if not sql.strip():
            return
        if "%(date_from)s" in sql or "%(date_to)s" in sql or "%(txn_id)s" in sql:
            return
        updated = apply_literal_dates_to_sql(sql, self.date_from.text(), self.date_to.text())
        if updated != sql:
            self.sql_editor.setPlainText(updated)

    def _report_kwargs(self, *, limit: int | None = None, offset: int | None = None) -> dict:
        if self.custom_sql_check.isChecked():
            mode = "custom"
        elif self.use_txn_id_check.isChecked() and self.txn_id.text().strip():
            mode = "txnId"
        else:
            mode = "date"
        kwargs = {
            "mode": mode,
            "date_from": self.date_from.text().strip() or None,
            "date_to": self.date_to.text().strip() or None,
            "txn_id": self.txn_id.text().strip() or None,
        }
        if mode == "custom":
            sql = self.sql_editor.toPlainText().strip()
            if "%(date_from)s" not in sql and "areq.messagedatetime >=" in sql.lower():
                sql = apply_literal_dates_to_sql(sql, self.date_from.text(), self.date_to.text())
            kwargs["sql"] = sql
        if limit is not None:
            kwargs["limit"] = limit
        if offset is not None:
            kwargs["offset"] = offset
        return kwargs

    def _run_report(self) -> None:
        self._report_offset = 0
        self._report_rows = []
        self._start_worker(
            ReportRunWorker(**self._report_kwargs(limit=CHUNK_SIZE, offset=0)),
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
        self._render_report_table()
        self._set_status(f"Preview: {len(self._report_rows):,} of {self._report_total:,} rows")
        self.report_header.set_badge(f"{self._report_total:,} rows")
        self.load_more_btn.setEnabled(len(self._report_rows) < self._report_total)

    def _append_report_page(self, result) -> None:
        self._report_rows.extend(result.rows)
        self._render_report_table()
        self._set_status(f"Preview: {len(self._report_rows):,} of {self._report_total:,} rows")
        self.load_more_btn.setEnabled(len(self._report_rows) < self._report_total)

    def _render_report_table(self) -> None:
        self.report_table.clear()
        self.report_table.setColumnCount(len(self._report_columns))
        self.report_table.setRowCount(len(self._report_rows))
        self.report_table.setHorizontalHeaderLabels(self._report_columns)
        for row_index, row in enumerate(self._report_rows):
            for col_index, column in enumerate(self._report_columns):
                value = str(row.get(column, ""))
                item = QTableWidgetItem(value)
                if "timeline" in column.lower() and len(value) > 80:
                    item.setToolTip(value[:500])
                self.report_table.setItem(row_index, col_index, item)
        self.report_table.resizeColumnsToContents()

    def _open_cell_detail(self, row: int, column: int) -> None:
        if column < 0 or column >= len(self._report_columns):
            return
        name = self._report_columns[column]
        if "timeline" not in name.lower():
            return
        item = self.report_table.item(row, column)
        if not item:
            return
        dialog = CellDetailDialog(name, item.text(), self)
        dialog.exec()

    def _export_report(self) -> None:
        self._start_worker(
            ReportExportWorker(**self._report_kwargs()),
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
            f"Saved {result.row_count:,} rows to:\n{path}\n\nFolder:\n{get_report_output_dir()}",
        )

    def _start_worker(
        self,
        worker,
        *,
        indeterminate: bool,
        for_parse: bool = False,
        on_progress=None,
        on_ok=None,
        status: str = "",
    ) -> None:
        if self._active_worker and self._active_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Another task is already running.")
            return
        self._active_worker = worker
        progress = self._active_progress(parse=for_parse)
        progress.setVisible(True)
        if indeterminate:
            progress.setRange(0, 0)
        else:
            progress.setRange(0, 100)
        if status:
            self._set_status(status, parse=for_parse)
        if on_progress:
            worker.progress.connect(on_progress)
        worker.finished_ok.connect(lambda payload=None: self._worker_done(on_ok, payload))
        worker.failed.connect(self._worker_failed)
        worker.start()

    def _active_progress(self, *, parse: bool = False) -> QProgressBar:
        return self.parse_progress if parse else self.report_progress

    def _worker_done(self, callback, payload) -> None:
        self.parse_progress.setVisible(False)
        self.report_progress.setVisible(False)
        self.parse_progress.setRange(0, 100)
        self.report_progress.setRange(0, 100)
        self._active_worker = None
        if callback:
            callback(payload) if payload is not None else callback()

    def _worker_failed(self, message: str) -> None:
        self.parse_progress.setVisible(False)
        self.report_progress.setVisible(False)
        self.parse_progress.setRange(0, 100)
        self.report_progress.setRange(0, 100)
        self._active_worker = None
        self.parse_status.setText("")
        self.report_status.setText("")
        QMessageBox.critical(self, "Error", message)

    def _set_progress(self, current: int, total: int, label: str, *, parse: bool = False) -> None:
        progress = self._active_progress(parse=parse)
        if total > 0:
            progress.setRange(0, total)
            progress.setValue(current)
        self._set_status(f"{label} ({current}/{total})" if total else label, parse=parse)

    def _set_status(self, text: str, *, parse: bool = False) -> None:
        if parse:
            self.parse_status.setText(text)
        else:
            self.report_status.setText(text)
