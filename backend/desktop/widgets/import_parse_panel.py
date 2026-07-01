from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from desktop.coverage_utils import (
    STATUS_FAILED,
    STATUS_MISSING,
    STATUS_PARSED,
    STATUS_PARTIAL,
    STATUS_PARSING,
    STATUS_READY,
    day_has_logs,
)
from desktop.widgets.common import danger_ghost_button, primary_button, secondary_button

STATUS_PILL_IDS = {
    STATUS_PARSED: "StatusPill",
    STATUS_READY: "StatusPillInfo",
    STATUS_PARSING: "StatusPillInfo",
    STATUS_PARTIAL: "StatusPillWarning",
    STATUS_MISSING: "StatusPillError",
    STATUS_FAILED: "StatusPillError",
}


class ImportDayCard(QFrame):
    delete_clicked = Signal(str)
    parse_clicked = Signal(str)

    def __init__(self, day: dict, *, busy: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._date = day["date"]
        self._can_delete = False
        self._can_parse = False
        self.setObjectName("ImportDayDetail")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        self.date_label = QLabel(day["date"])
        self.date_label.setObjectName("ImportDayDate")
        title_row.addWidget(self.date_label)
        title_row.addStretch()
        self.status_pill = QLabel("")
        self.status_pill.setObjectName("ImportDayStatusPill")
        title_row.addWidget(self.status_pill)
        layout.addLayout(title_row)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(12)

        rows_card = QFrame()
        rows_card.setObjectName("ImportMetricCard")
        rows_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rows_card_layout = QVBoxLayout(rows_card)
        rows_card_layout.setContentsMargins(12, 10, 12, 10)
        rows_card_layout.setSpacing(2)
        rows_caption = QLabel("Rows")
        rows_caption.setObjectName("ImportMetricCaption")
        self.rows_label = QLabel("")
        self.rows_label.setObjectName("ImportDayRows")
        rows_card_layout.addWidget(rows_caption)
        rows_card_layout.addWidget(self.rows_label)
        metrics_row.addWidget(rows_card, stretch=1)

        coverage_card = QFrame()
        coverage_card.setObjectName("ImportMetricCard")
        coverage_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        coverage_card_layout = QVBoxLayout(coverage_card)
        coverage_card_layout.setContentsMargins(12, 10, 12, 10)
        coverage_card_layout.setSpacing(2)
        coverage_caption = QLabel("Coverage")
        coverage_caption.setObjectName("ImportMetricCaption")
        self.coverage_label = QLabel("")
        self.coverage_label.setObjectName("ImportDayCoverage")
        coverage_card_layout.addWidget(coverage_caption)
        coverage_card_layout.addWidget(self.coverage_label)
        metrics_row.addWidget(coverage_card, stretch=1)

        layout.addLayout(metrics_row)

        self.error_frame = QFrame()
        self.error_frame.setObjectName("ImportDayErrorBox")
        error_layout = QVBoxLayout(self.error_frame)
        error_layout.setContentsMargins(12, 10, 12, 10)
        self.error_label = QLabel("")
        self.error_label.setObjectName("ImportDayError")
        self.error_label.setWordWrap(True)
        error_layout.addWidget(self.error_label)
        self.error_frame.setVisible(False)
        layout.addWidget(self.error_frame)

        actions = QHBoxLayout()
        actions.addStretch()
        self.parse_btn = secondary_button("Parse")
        self.parse_btn.clicked.connect(lambda: self.parse_clicked.emit(self._date))
        actions.addWidget(self.parse_btn)
        self.delete_btn = danger_ghost_button("Delete day data")
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._date))
        actions.addWidget(self.delete_btn)
        layout.addLayout(actions)

        self.populate(day)
        self.set_busy(busy)

    def populate(self, day: dict) -> None:
        self._date = day["date"]
        self.date_label.setText(day["date"])

        status = day.get("status", "")
        status_text = day.get("status_text", "")
        if status == STATUS_PARSED and day.get("complete"):
            status_text = "Parsed ✓"
        elif status == STATUS_PARTIAL or (day.get("csv_day") and not day.get("complete")):
            status_text = "Partial ⚠"

        self.status_pill.setText(status_text)
        pill_id = STATUS_PILL_IDS.get(status, "StatusPillMuted")
        self.status_pill.setObjectName(pill_id)
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)

        csv_day = day.get("csv_day")
        if csv_day:
            self.rows_label.setText(day.get("row_count_text", "—"))
            if day.get("complete") or csv_day.get("fullDay"):
                self.coverage_label.setText("Full day")
                self.coverage_label.setProperty("coverageKind", "full")
            else:
                self.coverage_label.setText("Partial day")
                self.coverage_label.setProperty("coverageKind", "partial")
        else:
            self.rows_label.setText("—")
            self.coverage_label.setText("Not parsed")
            self.coverage_label.setProperty("coverageKind", "none")

        self.coverage_label.style().unpolish(self.coverage_label)
        self.coverage_label.style().polish(self.coverage_label)

        log_day = day.get("log_day") or {}
        has_logs = day_has_logs(log_day)

        failed_message = day.get("failed_message", "")
        if failed_message:
            self.error_label.setText(failed_message)
            self.error_frame.setVisible(True)
        elif status == STATUS_MISSING and not has_logs:
            self.error_label.setText("No logs downloaded for this day")
            self.error_frame.setVisible(True)
        else:
            self.error_frame.setVisible(False)

        self._can_delete = has_logs or bool(csv_day)
        self._can_parse = has_logs
        self.parse_btn.setText("Re-parse" if csv_day else "Parse")

    def set_busy(self, busy: bool) -> None:
        self.delete_btn.setEnabled(self._can_delete and not busy)
        self.parse_btn.setEnabled(self._can_parse and not busy)


class ImportParsePanel(QWidget):
    download_requested = Signal(str, str)
    cancel_download_requested = Signal()
    parse_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImportParsePanel")
        self._busy = False
        self._day_cards: list[ImportDayCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.content_frame = QFrame()
        self.content_frame.setObjectName("ImportContentFrame")
        layout.addWidget(self.content_frame, stretch=1)

        inner = QVBoxLayout(self.content_frame)
        inner.setContentsMargins(20, 20, 20, 20)
        inner.setSpacing(14)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        title = QLabel("Import from Elastic")
        title.setObjectName("ImportPanelTitle")
        self.panel_title = title
        toolbar.addWidget(title)
        toolbar.addStretch()

        from_label = QLabel("From")
        from_label.setObjectName("FieldLabel")
        toolbar.addWidget(from_label)
        self.date_from = QDateEdit()
        self.date_from.setObjectName("ImportDateEdit")
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setMaximumDate(QDate.currentDate())
        self.date_from.setDate(QDate.currentDate().addDays(-1))
        toolbar.addWidget(self.date_from)

        to_label = QLabel("To")
        to_label.setObjectName("FieldLabel")
        toolbar.addWidget(to_label)
        self.date_to = QDateEdit()
        self.date_to.setObjectName("ImportDateEdit")
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setMaximumDate(QDate.currentDate())
        self.date_to.setDate(QDate.currentDate().addDays(-1))
        toolbar.addWidget(self.date_to)

        self.download_btn = primary_button("Download from Elastic")
        toolbar.addWidget(self.download_btn)
        inner.addLayout(toolbar)

        self.date_from.dateChanged.connect(self._sync_to_minimum)

        self.progress_box = QFrame()
        self.progress_box.setObjectName("ImportProgressBox")
        self.progress_box.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_box)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)

        self.progress_caption = QLabel("")
        self.progress_caption.setObjectName("ImportProgressCaption")
        self.progress_caption.setWordWrap(True)
        progress_layout.addWidget(self.progress_caption)

        self.progress = QProgressBar()
        self.progress.setObjectName("ImportProgress")
        self.progress.setFixedHeight(18)
        self.progress.setTextVisible(True)
        self.progress.setRange(0, 100)
        progress_layout.addWidget(self.progress)

        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        self.cancel_download_btn = danger_ghost_button("Stop download")
        self.cancel_download_btn.setVisible(False)
        self.cancel_download_btn.clicked.connect(self.cancel_download_requested.emit)
        cancel_row.addWidget(self.cancel_download_btn)
        progress_layout.addLayout(cancel_row)

        self.progress_list = QListWidget()
        self.progress_list.setObjectName("ImportProgressList")
        self.progress_list.setMaximumHeight(120)
        self.progress_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.progress_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.progress_list.setVisible(False)
        progress_layout.addWidget(self.progress_list)

        inner.addWidget(self.progress_box)

        self.message_label = QLabel("")
        self.message_label.setObjectName("ImportMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(False)
        inner.addWidget(self.message_label)

        self.content_area = QFrame()
        self.content_area.setObjectName("ImportContentArea")
        self.content_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        self.day_section = QLabel("Selected day")
        self.day_section.setObjectName("ImportSectionLabel")
        self.day_section.setVisible(False)
        content_layout.addWidget(self.day_section)

        self.days_scroll = QScrollArea()
        self.days_scroll.setObjectName("ImportDaysScroll")
        self.days_scroll.setWidgetResizable(True)
        self.days_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.days_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.days_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.days_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.days_scroll.setVisible(False)
        self.days_container = QWidget()
        self.days_container.setObjectName("ImportDaysContainer")
        self.days_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self.days_layout = QVBoxLayout(self.days_container)
        self.days_layout.setContentsMargins(0, 0, 0, 0)
        self.days_layout.setSpacing(10)
        self.days_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.days_scroll.setWidget(self.days_container)
        content_layout.addWidget(self.days_scroll, stretch=1)

        inner.addWidget(self.content_area, stretch=1)

        self.download_btn.clicked.connect(self._emit_download)

    def _sync_to_minimum(self, new_from: QDate) -> None:
        if self.date_to.date() < new_from:
            self.date_to.setDate(new_from)

    def _emit_download(self) -> None:
        if self._busy:
            return
        self.download_requested.emit(
            self.date_from.date().toString("yyyy-MM-dd"),
            self.date_to.date().toString("yyyy-MM-dd"),
        )

    def _clear_day_cards(self) -> None:
        for card in self._day_cards:
            card.deleteLater()
        self._day_cards.clear()
        while self.days_layout.count():
            item = self.days_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def set_days(self, days: list[dict]) -> None:
        self._clear_day_cards()

        if not days:
            self.day_section.setVisible(False)
            self.days_scroll.setVisible(False)
            return

        count = len(days)
        self.day_section.setText("Selected day" if count == 1 else f"Selected days ({count})")
        self.day_section.setVisible(True)
        self.days_scroll.setVisible(True)

        for day in days:
            card = ImportDayCard(day, busy=self._busy)
            card.delete_clicked.connect(self.delete_requested.emit)
            card.parse_clicked.connect(self.parse_requested.emit)
            self._day_cards.append(card)
            self.days_layout.addWidget(card)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.download_btn.setEnabled(not busy)
        self.date_from.setEnabled(not busy)
        self.date_to.setEnabled(not busy)
        for card in self._day_cards:
            card.set_busy(busy)

    def set_message(self, text: str, *, error: bool = False) -> None:
        self.message_label.setText(text)
        self.message_label.setVisible(bool(text))
        self.message_label.setProperty("error", error)
        self.message_label.setProperty("filled", bool(text))
        self.message_label.style().unpolish(self.message_label)
        self.message_label.style().polish(self.message_label)

    def clear_message(self) -> None:
        self.set_message("", error=False)

    def begin_progress(
        self,
        title: str,
        *,
        indeterminate: bool = False,
        phase: str = "",
    ) -> None:
        self.progress_list.clear()
        self.progress_list.setVisible(False)
        self.progress_caption.setText(title)
        if indeterminate:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        self._set_progress_phase(phase)
        self.cancel_download_btn.setVisible(phase == "download")
        self.cancel_download_btn.setEnabled(phase == "download")
        self.progress_box.setVisible(True)

    def update_progress(self, caption: str, percent: int, *, phase: str | None = None) -> None:
        self.progress_caption.setText(caption)
        if phase is not None:
            self._set_progress_phase(phase)
        if self.progress.maximum() != 0:
            self.progress.setValue(max(0, min(100, percent)))

    def _set_progress_phase(self, phase: str) -> None:
        value = phase or ""
        self.progress.setProperty("phase", value)
        self.progress_caption.setProperty("phase", value)
        for widget in (self.progress, self.progress_caption):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def add_progress_item(self, text: str) -> None:
        self.progress_list.addItem(text)
        self.progress_list.setVisible(True)
        self.progress_list.scrollToBottom()

    def set_cancel_download_enabled(self, enabled: bool) -> None:
        self.cancel_download_btn.setEnabled(enabled)

    def end_progress(self) -> None:
        self.progress_box.setVisible(False)
        self.progress_caption.setText("")
        self.progress_list.clear()
        self.progress_list.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.cancel_download_btn.setVisible(False)
        self._set_progress_phase("")
