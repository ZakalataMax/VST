from __future__ import annotations

import json
import re

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.services.report_mailer import recipients_from_env
from app.services.report import format_report_cell_value, format_report_datetime_field
from desktop.report_sql_utils import build_report_sql_from_filters
from desktop.report_table_utils import default_column_width, should_elide
from desktop.widgets.common import ghost_button, primary_button, secondary_button

SETTINGS_ORG = "VST"
SETTINGS_APP = "WorkTools"
COLUMN_WIDTHS_KEY = "report/column_widths"


class ElideDelegate(QStyledItemDelegate):
    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:
        super().initStyleOption(option, index)
        option.textElideMode = Qt.TextElideMode.ElideRight


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


class CustomSqlDialog(QDialog):
    reset_requested = Signal()
    sql_edited_by_user = Signal(str)
    applied = Signal(bool, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom SQL")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.resize(860, 560)
        self._programmatic = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header = QLabel("Custom SQL")
        header.setObjectName("CardTitle")
        header_row.addWidget(header)
        header_row.addStretch()

        self.refresh_btn = QToolButton()
        self.refresh_btn.setObjectName("ReportChevron")
        self.refresh_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_btn.setToolTip("Reset SQL and filters to default")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.clicked.connect(self.reset_requested.emit)
        header_row.addWidget(self.refresh_btn)
        layout.addLayout(header_row)

        hint = QLabel("Filters update the query below. Edit manually or reset to the default template.")
        hint.setObjectName("MutedLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.use_custom_check = QCheckBox("Use custom SQL for report")
        layout.addWidget(self.use_custom_check)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("SELECT or WITH …")
        self.editor.setMinimumHeight(360)
        self.editor.textChanged.connect(self._on_editor_changed)
        layout.addWidget(self.editor, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close | QDialogButtonBox.StandardButton.Apply
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText("Apply")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Close")
        buttons.rejected.connect(self.close)
        buttons.accepted.connect(self._emit_apply)
        layout.addWidget(buttons)

    def set_sql(self, sql: str) -> None:
        self._programmatic = True
        self.editor.setPlainText(sql)
        self._programmatic = False

    def set_use_custom(self, enabled: bool) -> None:
        self.use_custom_check.setChecked(enabled)

    def _on_editor_changed(self) -> None:
        if self._programmatic:
            return
        self.sql_edited_by_user.emit(self.editor.toPlainText())

    def _emit_apply(self) -> None:
        self.applied.emit(self.use_custom_check.isChecked(), self.editor.toPlainText().strip())

    def closeEvent(self, event) -> None:
        self._emit_apply()
        super().closeEvent(event)


class EmailComposeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Email report")
        self.resize(560, 440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        header = QLabel("Email report")
        header.setObjectName("CardTitle")
        layout.addWidget(header)

        self.range_label = QLabel("")
        self.range_label.setObjectName("MutedLabel")
        layout.addWidget(self.range_label)

        to_row = QHBoxLayout()
        to_row.setSpacing(8)
        to_row.addWidget(QLabel("To:"))
        self.recipients_field = QLineEdit()
        self.recipients_field.setPlaceholderText("name@company.com, ...")
        to_row.addWidget(self.recipients_field, stretch=1)
        layout.addLayout(to_row)

        self.body_edit = QPlainTextEdit()
        self.body_edit.setMinimumHeight(240)
        layout.addWidget(self.body_edit, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Send")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_date_range_text(self, text: str) -> None:
        self.range_label.setText(f"Range: {text}")

    def set_recipients(self, text: str) -> None:
        self.recipients_field.setText(text)

    def recipients(self) -> list[str]:
        return [part.strip() for part in re.split(r"[,;]", self.recipients_field.text()) if part.strip()]

    def set_body(self, text: str) -> None:
        self.body_edit.setPlainText(text)

    def body(self) -> str:
        return self.body_edit.toPlainText()


class ReportPanel(QWidget):
    run_requested = Signal()
    export_requested = Signal()
    load_more_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReportPanel")
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        self._report_columns: list[str] = []
        self._custom_sql_enabled = False
        self._custom_sql_text = ""
        self._sql_manual = False
        self._syncing_filters = False
        self._custom_sql_dialog: CustomSqlDialog | None = None
        self._has_results = False
        self._last_email_recipients = ""
        self._last_email_body = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        filter_bar = QFrame()
        filter_bar.setObjectName("ReportToolbar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(14, 10, 14, 10)
        filter_layout.setSpacing(10)

        self.date_from = QLineEdit()
        self.date_from.setObjectName("ReportField")
        self.date_from.setPlaceholderText("2026-06-03 00:00:00")
        self.date_from.setFixedSize(178, 32)
        self.date_from.textChanged.connect(self._on_filters_changed)
        filter_layout.addWidget(self.date_from)

        dash = QLabel("–")
        dash.setObjectName("ReportRangeDash")
        dash.setFixedWidth(10)
        dash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filter_layout.addWidget(dash)

        self.date_to = QLineEdit()
        self.date_to.setObjectName("ReportField")
        self.date_to.setPlaceholderText("2026-06-03 23:59:59")
        self.date_to.setFixedSize(178, 32)
        self.date_to.textChanged.connect(self._on_filters_changed)
        filter_layout.addWidget(self.date_to)

        divider_dates = QFrame()
        divider_dates.setObjectName("ReportDivider")
        divider_dates.setFixedSize(1, 24)
        filter_layout.addWidget(divider_dates)

        self.use_txn_id_check = QCheckBox("Txn ID")
        self.use_txn_id_check.toggled.connect(self._on_txn_filter_toggled)
        filter_layout.addWidget(self.use_txn_id_check)

        self.txn_id = QLineEdit()
        self.txn_id.setObjectName("ReportField")
        self.txn_id.setPlaceholderText("Transaction ID")
        self.txn_id.setFixedSize(200, 32)
        self.txn_id.textChanged.connect(self._on_filters_changed)
        self.txn_id.setVisible(False)
        filter_layout.addWidget(self.txn_id)

        divider_opts = QFrame()
        divider_opts.setObjectName("ReportDivider")
        divider_opts.setFixedSize(1, 24)
        filter_layout.addWidget(divider_opts)

        self.custom_sql_btn = ghost_button("Custom SQL…")
        self.custom_sql_btn.setObjectName("CompactGhostButton")
        self.custom_sql_btn.setFixedHeight(32)
        self.custom_sql_btn.clicked.connect(self._open_custom_sql_dialog)
        filter_layout.addWidget(self.custom_sql_btn)

        self.custom_sql_indicator = QLabel("")
        self.custom_sql_indicator.setObjectName("ReportSqlIndicator")
        filter_layout.addWidget(self.custom_sql_indicator)

        filter_layout.addStretch()

        self.run_btn = primary_button("Run")
        self.run_btn.setObjectName("CompactPrimaryButton")
        self.run_btn.setFixedSize(72, 32)
        self.run_btn.clicked.connect(self.run_requested.emit)
        filter_layout.addWidget(self.run_btn)

        root.addWidget(filter_bar)

        self.progress = QProgressBar()
        self.progress.setObjectName("ReportProgress")
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.content_area = QWidget()
        self.content_area.setObjectName("ReportContent")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.empty_state = QFrame()
        self.empty_state.setObjectName("ReportEmptyState")
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_hint = QLabel("Set From / To with time (YYYY-MM-DD HH:MM:SS) and click Run.")
        empty_hint.setObjectName("MutedLabel")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint.setWordWrap(True)
        empty_layout.addStretch()
        empty_layout.addWidget(empty_hint)
        empty_layout.addStretch()
        content_layout.addWidget(self.empty_state, stretch=1)

        self.results_frame = QFrame()
        self.results_frame.setObjectName("ReportResults")
        self.results_frame.setVisible(False)
        results_layout = QVBoxLayout(self.results_frame)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(0)

        results_bar = QFrame()
        results_bar.setObjectName("ReportResultsBar")
        results_bar_layout = QHBoxLayout(results_bar)
        results_bar_layout.setContentsMargins(14, 8, 10, 8)
        results_bar_layout.setSpacing(10)
        results_title = QLabel("Preview")
        results_title.setObjectName("ReportResultsTitle")
        results_bar_layout.addWidget(results_title)

        self.total_badge = QLabel("")
        self.total_badge.setObjectName("Badge")
        self.total_badge.setVisible(False)
        results_bar_layout.addWidget(self.total_badge)

        self.shown_badge = QLabel("")
        self.shown_badge.setObjectName("BadgeInfo")
        self.shown_badge.setVisible(False)
        results_bar_layout.addWidget(self.shown_badge)

        results_bar_layout.addStretch()
        self.close_results_btn = QToolButton()
        self.close_results_btn.setObjectName("ReportCloseButton")
        self.close_results_btn.setText("×")
        self.close_results_btn.setToolTip("Close report preview")
        self.close_results_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_results_btn.clicked.connect(self._close_results)
        results_bar_layout.addWidget(self.close_results_btn)
        results_layout.addWidget(results_bar)

        self.report_table = QTableWidget()
        self.report_table.setObjectName("ReportTable")
        self.report_table.setAlternatingRowColors(True)
        self.report_table.setShowGrid(False)
        self.report_table.verticalHeader().setVisible(False)
        self.report_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.report_table.setWordWrap(False)
        self.report_table.setFont(QFont("Segoe UI", 9))
        self.report_table.cellDoubleClicked.connect(self._open_cell_detail)

        header = self.report_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setFixedHeight(26)
        header.sectionHandleDoubleClicked.connect(self._fit_column_to_contents)
        header.sectionResized.connect(self._on_column_resized)
        self.report_table.setItemDelegate(ElideDelegate(self.report_table))
        results_layout.addWidget(self.report_table, stretch=1)

        footer = QFrame()
        footer.setObjectName("ReportFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 8, 14, 10)
        footer_layout.setSpacing(10)

        self.report_status = QLabel("")
        self.report_status.setObjectName("MutedLabel")
        footer_layout.addWidget(self.report_status)
        footer_layout.addStretch()

        self.native_pivot_check = QCheckBox("Native pivot")
        self.native_pivot_check.setChecked(True)
        self.native_pivot_check.setToolTip(
            "Build a live Excel PivotTable on export via Excel automation (requires Excel "
            "to be installed)."
        )
        footer_layout.addWidget(self.native_pivot_check)

        self.email_check = QCheckBox("Email report")
        self.email_check.setChecked(True)
        self.email_check.setToolTip(
            "Compose and email the exported file on export via the local Outlook app."
        )
        footer_layout.addWidget(self.email_check)

        self.export_btn = secondary_button("Export")
        self.export_btn.setObjectName("CompactSecondaryButton")
        self.export_btn.setFixedHeight(28)
        self.export_btn.clicked.connect(self.export_requested.emit)
        self.export_btn.setVisible(False)
        footer_layout.addWidget(self.export_btn)

        self.load_more_btn = secondary_button("Load more")
        self.load_more_btn.setObjectName("CompactSecondaryButton")
        self.load_more_btn.setFixedHeight(28)
        self.load_more_btn.clicked.connect(self.load_more_requested.emit)
        footer_layout.addWidget(self.load_more_btn)
        results_layout.addWidget(footer)

        content_layout.addWidget(self.results_frame, stretch=1)
        root.addWidget(self.content_area, stretch=1)

        self._rebuild_sql_from_filters()
        self._update_custom_sql_indicator()
        self._sync_content_view()

    def uses_custom_sql(self) -> bool:
        return self._custom_sql_enabled

    def uses_txn_filter(self) -> bool:
        return self.use_txn_id_check.isChecked() and bool(self.txn_id.text().strip())

    def native_pivot_enabled(self) -> bool:
        return self.native_pivot_check.isChecked()

    def email_enabled(self) -> bool:
        return self.email_check.isChecked()

    def compose_email(self, *, default_body: str, date_range_text: str) -> tuple[list[str], str] | None:
        dialog = EmailComposeDialog(parent=self.window())
        dialog.set_date_range_text(date_range_text)
        dialog.set_recipients(self._last_email_recipients or ", ".join(recipients_from_env()))
        dialog.set_body(self._last_email_body or default_body)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        recipients = dialog.recipients()
        body = dialog.body()
        self._last_email_recipients = ", ".join(recipients)
        self._last_email_body = body
        return recipients, body

    def custom_sql(self) -> str:
        return self._custom_sql_text.strip()

    def set_date_range(self, date_from: str, date_to: str) -> None:
        self._syncing_filters = True
        self.date_from.setText(format_report_datetime_field(date_from, end=False))
        self.date_to.setText(format_report_datetime_field(date_to, end=True))
        self._syncing_filters = False
        self._on_filters_changed()

    def set_export_visible(self, visible: bool) -> None:
        self.export_btn.setVisible(visible)

    def prepare_run(self) -> None:
        self.set_export_visible(False)
        self.set_total_rows(0)
        self.set_shown_rows(0, 0)
        self.set_load_more_enabled(False)
        self._has_results = False
        self.report_table.clear()
        self.report_table.setRowCount(0)
        self.report_table.setColumnCount(0)
        self._report_columns = []
        self.set_status("")
        self._sync_content_view()

    def clear_results(self) -> None:
        self.prepare_run()

    def _sync_content_view(self) -> None:
        self.empty_state.setVisible(not self._has_results)
        self.results_frame.setVisible(self._has_results)

    def _close_results(self) -> None:
        if not self._has_results:
            return
        reply = QMessageBox.question(
            self,
            "Close report",
            "Close the report preview?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.clear_results()

    def set_progress_visible(self, visible: bool) -> None:
        self.progress.setVisible(visible)
        if not visible:
            self.progress.setRange(0, 100)

    def set_status(self, text: str) -> None:
        self.report_status.setText(text)

    def set_total_rows(self, total: int) -> None:
        if total > 0:
            self.total_badge.setText(f"{total:,} rows")
            self.total_badge.setVisible(True)
        else:
            self.total_badge.setVisible(False)

    def set_shown_rows(self, shown: int, total: int) -> None:
        if total > 0:
            self.shown_badge.setText(f"{shown:,} shown")
            self.shown_badge.setVisible(True)
        else:
            self.shown_badge.setVisible(False)

    def set_load_more_enabled(self, enabled: bool) -> None:
        self.load_more_btn.setEnabled(enabled)

    def render_table(self, columns: list[str], rows: list[dict]) -> None:
        self._report_columns = columns
        self.report_table.clear()
        self.report_table.setColumnCount(len(columns))
        self.report_table.setRowCount(len(rows))
        self.report_table.setHorizontalHeaderLabels(columns)

        mono_columns = {
            index
            for index, column in enumerate(columns)
            if any(token in column.lower() for token in ("transid", "agent", "timeline", "uuid"))
        }

        for row_index, row in enumerate(rows):
            for col_index, column in enumerate(columns):
                raw_value = str(row.get(column, ""))
                value = format_report_cell_value(column, raw_value)
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if should_elide(column, value):
                    item.setToolTip(value[:2000])
                if col_index in mono_columns:
                    item.setFont(QFont("Consolas", 9))
                self.report_table.setItem(row_index, col_index, item)

        self._apply_column_widths(columns)
        self._has_results = True
        self._sync_content_view()

    def _filter_values(self) -> tuple[str, str, str, bool]:
        return (
            self.date_from.text().strip(),
            self.date_to.text().strip(),
            self.txn_id.text().strip(),
            self.use_txn_id_check.isChecked(),
        )

    def _rebuild_sql_from_filters(self) -> str:
        date_from, date_to, txn_id, filter_by_txn = self._filter_values()
        sql = build_report_sql_from_filters(
            date_from=date_from,
            date_to=date_to or date_from,
            txn_id=txn_id,
            filter_by_txn=filter_by_txn,
        )
        self._custom_sql_text = sql
        return sql

    def _sync_custom_sql_dialog(self) -> None:
        if not self._custom_sql_dialog:
            return
        self._custom_sql_dialog.set_sql(self._custom_sql_text)
        self._custom_sql_dialog.set_use_custom(self._custom_sql_enabled)

    def _invalidate_results(self) -> None:
        if self._has_results:
            self.clear_results()

    def _on_filters_changed(self) -> None:
        if self._syncing_filters:
            return
        if not self._sql_manual:
            self._rebuild_sql_from_filters()
            self._sync_custom_sql_dialog()
        self._update_custom_sql_indicator()
        self._invalidate_results()

    def _on_txn_filter_toggled(self, checked: bool) -> None:
        self.txn_id.setVisible(checked)
        if not checked:
            self._syncing_filters = True
            self.txn_id.clear()
            self._syncing_filters = False
        self._on_filters_changed()

    def _reset_sql_and_filters(self) -> None:
        self._sql_manual = False
        self._custom_sql_enabled = False
        self._syncing_filters = True
        self.use_txn_id_check.setChecked(False)
        self.txn_id.clear()
        self._syncing_filters = False
        self.txn_id.setVisible(False)
        self._rebuild_sql_from_filters()
        self._sync_custom_sql_dialog()
        self._update_custom_sql_indicator()
        self._invalidate_results()

    def _open_custom_sql_dialog(self) -> None:
        if not self._sql_manual:
            self._rebuild_sql_from_filters()
        if self._custom_sql_dialog is None:
            dialog = CustomSqlDialog(parent=self.window())
            dialog.reset_requested.connect(self._reset_sql_and_filters)
            dialog.sql_edited_by_user.connect(self._on_dialog_sql_edited)
            dialog.applied.connect(self._on_dialog_applied)
            dialog.finished.connect(lambda _code: setattr(self, "_custom_sql_dialog", None))
            self._custom_sql_dialog = dialog
        self._custom_sql_dialog.set_use_custom(self._custom_sql_enabled)
        self._custom_sql_dialog.set_sql(self._custom_sql_text)
        self._custom_sql_dialog.show()
        self._custom_sql_dialog.raise_()
        self._custom_sql_dialog.activateWindow()

    def _on_dialog_sql_edited(self, sql: str) -> None:
        self._sql_manual = True
        self._custom_sql_enabled = True
        self._custom_sql_text = sql.strip()
        if self._custom_sql_dialog:
            self._custom_sql_dialog.set_use_custom(True)
        self._update_custom_sql_indicator()
        self._invalidate_results()

    def _on_dialog_applied(self, enabled: bool, sql: str) -> None:
        self._custom_sql_enabled = enabled
        self._custom_sql_text = sql.strip()
        auto_sql = build_report_sql_from_filters(
            date_from=self.date_from.text().strip(),
            date_to=self.date_to.text().strip() or self.date_from.text().strip(),
            txn_id=self.txn_id.text().strip(),
            filter_by_txn=self.use_txn_id_check.isChecked(),
        )
        self._sql_manual = sql.strip() != auto_sql.strip()
        self._update_custom_sql_indicator()
        self._invalidate_results()

    def _update_custom_sql_indicator(self) -> None:
        if self._custom_sql_enabled and self._custom_sql_text.strip():
            self.custom_sql_indicator.setText("Active")
            self.custom_sql_indicator.setVisible(True)
        else:
            self.custom_sql_indicator.setVisible(False)

    def _load_saved_widths(self) -> dict[str, int]:
        raw = self._settings.value(COLUMN_WIDTHS_KEY, "")
        if not raw:
            return {}
        if isinstance(raw, dict):
            return {str(key): int(value) for key, value in raw.items()}
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(key): int(value) for key, value in parsed.items()}

    def _save_column_widths(self) -> None:
        if not self._report_columns:
            return
        widths = {
            column: self.report_table.columnWidth(index)
            for index, column in enumerate(self._report_columns)
        }
        self._settings.setValue(COLUMN_WIDTHS_KEY, json.dumps(widths))

    def _apply_column_widths(self, columns: list[str]) -> None:
        saved = self._load_saved_widths()
        for index, column in enumerate(columns):
            width = saved.get(column, default_column_width(column))
            self.report_table.setColumnWidth(index, max(width, 48))

    def _fit_column_to_contents(self, index: int) -> None:
        if index < 0 or index >= self.report_table.columnCount():
            return
        self.report_table.resizeColumnToContents(index)
        width = self.report_table.columnWidth(index)
        self.report_table.setColumnWidth(index, min(max(width + 16, 48), 480))
        self._save_column_widths()

    def _on_column_resized(self, _index: int, _old: int, _new: int) -> None:
        self._save_column_widths()

    def _open_cell_detail(self, row: int, column: int) -> None:
        if column < 0 or column >= len(self._report_columns):
            return
        item = self.report_table.item(row, column)
        if not item or not item.text():
            return
        dialog = CellDetailDialog(self._report_columns[column], item.text(), self)
        dialog.exec()
