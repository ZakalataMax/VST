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
    QSplitter,
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
        content_layout.setSpacing(16)

        content_layout.addWidget(self._build_parse_card())
        content_layout.addWidget(self._build_report_card(), stretch=1)
        root.addWidget(content, stretch=1)

        self.refresh_data()

    def _build_parse_card(self) -> Card:
        card = Card()
        card.add_widget(SectionHeader("Parse & Import"))

        upload_row = QHBoxLayout()
        upload_btn = primary_button("Upload logs…")
        upload_btn.clicked.connect(self._upload_logs)
        refresh_btn = secondary_button("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        upload_row.addWidget(upload_btn)
        upload_row.addWidget(refresh_btn)
        upload_row.addStretch()
        card.add_layout(upload_row)

        card.add_widget(field_label("Stored log files"))
        self.saved_files_list = QListWidget()
        self.saved_files_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.saved_files_list.setMinimumHeight(120)
        card.add_widget(self.saved_files_list)

        queue_row = QHBoxLayout()
        add_queue_btn = secondary_button("Add to queue")
        add_queue_btn.clicked.connect(self._add_to_queue)
        clear_queue_btn = ghost_button("Clear queue")
        clear_queue_btn.clicked.connect(self._clear_queue)
        parse_btn = primary_button("Parse queue")
        parse_btn.clicked.connect(self._parse_queue)
        queue_row.addWidget(add_queue_btn)
        queue_row.addWidget(clear_queue_btn)
        queue_row.addStretch()
        queue_row.addWidget(parse_btn)
        card.add_layout(queue_row)

        card.add_widget(field_label("Parse queue"))
        self.queue_list = QListWidget()
        self.queue_list.setMinimumHeight(72)
        card.add_widget(self.queue_list)
        return card

    def _build_report_card(self) -> Card:
        card = Card()
        self.report_header = SectionHeader("Report")
        card.add_widget(self.report_header)

        form = QFormLayout()
        form.setSpacing(10)
        self.date_from = QLineEdit()
        self.date_to = QLineEdit()
        self.txn_id = QLineEdit()
        self.date_from.setPlaceholderText("2026-05-27")
        self.date_to.setPlaceholderText("2026-05-29")
        self.date_from.textChanged.connect(lambda: self._apply_dates_to_sql())
        self.date_to.textChanged.connect(lambda: self._apply_dates_to_sql())
        form.addRow(field_label("From"), self.date_from)
        form.addRow(field_label("To"), self.date_to)
        form.addRow(field_label("Transaction ID"), self.txn_id)
        card.add_layout(form)

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
        self.sql_editor.setMinimumHeight(140)
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

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedHeight(6)
        card.add_widget(self.progress)

        self.report_table = QTableWidget()
        self.report_table.setAlternatingRowColors(True)
        self.report_table.setShowGrid(False)
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.report_table.cellDoubleClicked.connect(self._open_cell_detail)
        card.add_widget(self.report_table)
        return card

    def refresh_data(self) -> None:
        self._files = list_log_files()
        log_days = list_log_days()
        csv_days = list_csv_days()
        self._coverage_days = build_coverage_days(self._files, log_days, csv_days)
        self._render_coverage()
        self._render_saved_files()

    def _coverage_summary(self) -> str:
        with_logs = with_pair = complete = parsed = total_rows = 0
        for day in self._coverage_days:
            log_day = day.get("log_day") or {}
            csv_day = day.get("csv_day")
            if log_day.get("acs1") or log_day.get("acs2"):
                with_logs += 1
            if log_day.get("acs1") and log_day.get("acs2"):
                with_pair += 1
            if day.get("complete"):
                complete += 1
            if csv_day:
                parsed += 1
                total_rows += int(csv_day.get("rowCount") or 0)
        return (
            f"{len(self._coverage_days)} days · {with_pair} pairs · "
            f"{complete} complete · {total_rows:,} rows"
        )

    def _render_coverage(self) -> None:
        self.sidebar.set_days(self._coverage_days, self._coverage_summary())

    def _render_saved_files(self) -> None:
        self.saved_files_list.clear()
        for file in sorted(self._files, key=lambda item: (item.get("logDate", ""), item.get("acsNode", ""))):
            node = (file.get("acsNode") or "").upper()
            label = f"{file.get('logDate')}   {node}   {file.get('filename')}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, file["id"])
            item.setToolTip(file.get("filename", ""))
            font = item.font()
            font.setWeight(600 if file.get("acsNode") == "acs1" else 500)
            item.setFont(font)
            self.saved_files_list.addItem(item)

    def _on_coverage_selected(self, date: str) -> None:
        self.sidebar.set_selected_date(date)
        self.date_from.setText(date)
        self.date_to.setText(date)
        if self.custom_sql_check.isChecked():
            self._apply_dates_to_sql()

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
            on_progress=lambda current, total, name: self._set_progress(current, total, f"Uploading {name}"),
            on_ok=lambda: (self.refresh_data(), self._set_status("Upload complete.")),
        )

    def _add_to_queue(self) -> None:
        selected = self.saved_files_list.selectedItems()
        if not selected:
            return
        existing = {self.queue_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queue_list.count())}
        for item in selected:
            file_id = item.data(Qt.ItemDataRole.UserRole)
            if file_id in existing:
                continue
            self.queue_list.addItem(QListWidgetItem(item.text()))
            self.queue_list.item(self.queue_list.count() - 1).setData(Qt.ItemDataRole.UserRole, file_id)
        self._queue_ids = [
            self.queue_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queue_list.count())
        ]

    def _clear_queue(self) -> None:
        self.queue_list.clear()
        self._queue_ids = []

    def _parse_queue(self) -> None:
        self._queue_ids = [
            self.queue_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queue_list.count())
        ]
        if not self._queue_ids:
            QMessageBox.warning(self, "Parse", "Parse queue is empty.")
            return
        error = _validate_queue_pairs(self._queue_ids, self._files)
        if error:
            QMessageBox.warning(self, "Parse", error)
            return
        self._start_worker(
            ParseLogsWorker(self._queue_ids),
            indeterminate=True,
            on_progress=lambda current, total, label: self._set_progress(current, total, label),
            on_ok=lambda saved: (
                self.refresh_data(),
                self._clear_queue(),
                self._set_status(f"Parsed {len(saved)} day(s)."),
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
        on_progress=None,
        on_ok=None,
        status: str = "",
    ) -> None:
        if self._active_worker and self._active_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Another task is already running.")
            return
        self._active_worker = worker
        self.progress.setVisible(True)
        if indeterminate:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
        if status:
            self._set_status(status)
        if on_progress:
            worker.progress.connect(on_progress)
        worker.finished_ok.connect(lambda payload=None: self._worker_done(on_ok, payload))
        worker.failed.connect(self._worker_failed)
        worker.start()

    def _worker_done(self, callback, payload) -> None:
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self._active_worker = None
        if callback:
            callback(payload) if payload is not None else callback()

    def _worker_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self._active_worker = None
        self._set_status("")
        QMessageBox.critical(self, "Error", message)

    def _set_progress(self, current: int, total: int, label: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
        self._set_status(f"{label} ({current}/{total})" if total else label)

    def _set_status(self, text: str) -> None:
        self.report_status.setText(text)
