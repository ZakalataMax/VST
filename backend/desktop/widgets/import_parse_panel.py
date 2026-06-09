from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt, Signal
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QPainter,
    QPen,
    QPolygonF,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
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
)
from desktop.widgets.common import danger_ghost_button, primary_button

STATUS_PILL_IDS = {
    STATUS_PARSED: "StatusPill",
    STATUS_READY: "StatusPillInfo",
    STATUS_PARSING: "StatusPillInfo",
    STATUS_PARTIAL: "StatusPillWarning",
    STATUS_MISSING: "StatusPillError",
    STATUS_FAILED: "StatusPillError",
}


def _paths_from_drop(event: QDropEvent) -> list[str]:
    paths: list[str] = []
    for url in event.mimeData().urls():
        if url.isLocalFile():
            path = url.toLocalFile()
            if path:
                paths.append(path)
    return paths


class ImportDayCard(QFrame):
    delete_clicked = Signal(str)

    def __init__(self, day: dict, *, busy: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._date = day["date"]
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

        failed_message = day.get("failed_message", "")
        if failed_message:
            self.error_label.setText(failed_message)
            self.error_frame.setVisible(True)
        elif status == STATUS_MISSING:
            log_day = day.get("log_day") or {}
            missing = [node.upper() for node in ("acs1", "acs2") if not log_day.get(node)]
            if missing:
                self.error_label.setText(f"Missing {', '.join(missing)} log")
                self.error_frame.setVisible(True)
            else:
                self.error_frame.setVisible(False)
        else:
            self.error_frame.setVisible(False)

        has_data = bool(day.get("log_day")) or bool(csv_day)
        self._can_delete = has_data

    def set_busy(self, busy: bool) -> None:
        self.delete_btn.setEnabled(self._can_delete and not busy)


class DropFileIcon(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(80, 96)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        doc_left = 14.0
        doc_top = 8.0
        doc_width = 44.0
        doc_height = 56.0
        fold = 12.0

        painter.setPen(QPen(Qt.GlobalColor.white, 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(int(doc_left), int(doc_top), int(doc_width), int(doc_height), 6, 6)

        fold_path = QPolygonF(
            [
                QPointF(doc_left + doc_width - fold, doc_top),
                QPointF(doc_left + doc_width, doc_top + fold),
                QPointF(doc_left + doc_width - fold, doc_top + fold),
            ]
        )
        painter.drawPolyline(fold_path)

        line_pen = QPen(Qt.GlobalColor.white, 1.5)
        painter.setPen(line_pen)
        line_left = doc_left + 10
        line_right = doc_left + doc_width - 10
        for index, y in enumerate((doc_top + 22, doc_top + 32, doc_top + 42)):
            if index == 2:
                line_right -= 8
            painter.drawLine(int(line_left), int(y), int(line_right), int(y))

        badge_center_x = doc_left + doc_width / 2
        badge_center_y = doc_top + doc_height + 14
        badge_radius = 14.0
        painter.setPen(QPen(Qt.GlobalColor.white, 2.0))
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawEllipse(
            int(badge_center_x - badge_radius),
            int(badge_center_y - badge_radius),
            int(badge_radius * 2),
            int(badge_radius * 2),
        )

        plus_pen = QPen(Qt.GlobalColor.black, 2.2)
        painter.setPen(plus_pen)
        plus_size = 7.0
        painter.drawLine(
            int(badge_center_x - plus_size),
            int(badge_center_y),
            int(badge_center_x + plus_size),
            int(badge_center_y),
        )
        painter.drawLine(
            int(badge_center_x),
            int(badge_center_y - plus_size),
            int(badge_center_x),
            int(badge_center_y + plus_size),
        )


class ImportParsePanel(QWidget):
    load_requested = Signal()
    files_dropped = Signal(list)
    delete_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImportParsePanel")
        self.setAcceptDrops(True)
        self._drag_active = False
        self._drag_depth = 0
        self._busy = False
        self._day_cards: list[ImportDayCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.drop_zone = QFrame()
        self.drop_zone.setObjectName("ImportDropZone")
        self.drop_zone.setAcceptDrops(True)
        layout.addWidget(self.drop_zone, stretch=1)

        inner = QVBoxLayout(self.drop_zone)
        inner.setContentsMargins(20, 20, 20, 20)
        inner.setSpacing(14)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        title = QLabel("Import")
        title.setObjectName("ImportPanelTitle")
        self.panel_title = title
        toolbar.addWidget(title)
        toolbar.addStretch()
        self.load_btn = primary_button("Load logs")
        toolbar.addWidget(self.load_btn)
        inner.addLayout(toolbar)

        self.progress = QProgressBar()
        self.progress.setObjectName("ImportProgress")
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        inner.addWidget(self.progress)

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

        self.drag_overlay = QFrame(self)
        self.drag_overlay.setObjectName("ImportDragOverlay")
        self.drag_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.drag_overlay.setVisible(False)
        overlay_layout = QVBoxLayout(self.drag_overlay)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.addStretch()
        self.drop_icon = DropFileIcon()
        overlay_layout.addWidget(self.drop_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch()

        self.load_btn.clicked.connect(self.load_requested.emit)
        self._install_drag_filters(self.drop_zone)
        self.installEventFilter(self)
        self.drag_overlay.installEventFilter(self)
        self.drop_icon.installEventFilter(self)

    def _install_drag_filters(self, root: QWidget) -> None:
        root.installEventFilter(self)
        for child in root.findChildren(QWidget):
            child.installEventFilter(self)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._sync_drag_overlay()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_drag_overlay()

    def _sync_drag_overlay(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return
        self.drag_overlay.setGeometry(0, 0, self.width(), self.height())
        if self._drag_active:
            self.drag_overlay.raise_()

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
            self._day_cards.append(card)
            self.days_layout.addWidget(card)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.load_btn.setEnabled(not busy)
        for card in self._day_cards:
            card.set_busy(busy)
        if not busy:
            self._set_drag_active(False)

    def set_message(self, text: str, *, error: bool = False) -> None:
        self.message_label.setText(text)
        self.message_label.setVisible(bool(text))
        self.message_label.setProperty("error", error)
        self.message_label.setProperty("filled", bool(text))
        self.message_label.style().unpolish(self.message_label)
        self.message_label.style().polish(self.message_label)

    def clear_message(self) -> None:
        self.set_message("", error=False)

    def set_progress(self, *, visible: bool, current: int = 0, total: int = 0) -> None:
        self.progress.setVisible(visible)
        if not visible:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            return
        if total <= 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, total)
            self.progress.setValue(current)

    def _set_drag_active(self, active: bool) -> None:
        if self._drag_active == active:
            return
        self._drag_active = active
        self.drop_zone.setProperty("dragActive", active)
        self.drop_zone.style().unpolish(self.drop_zone)
        self.drop_zone.style().polish(self.drop_zone)
        if active:
            self._sync_drag_overlay()
            self.drag_overlay.setVisible(True)
            self.drag_overlay.raise_()
        else:
            self.drag_overlay.setVisible(False)

    def _accept_drag(self, event: QDragEnterEvent | QDragMoveEvent) -> bool:
        if self._busy or not event.mimeData().hasUrls():
            event.ignore()
            return False
        event.acceptProposedAction()
        return True

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (
            QEvent.Type.DragEnter,
            QEvent.Type.DragMove,
            QEvent.Type.DragLeave,
            QEvent.Type.Drop,
        ):
            if event.type() == QEvent.Type.DragEnter:
                self.dragEnterEvent(event)
            elif event.type() == QEvent.Type.DragMove:
                self.dragMoveEvent(event)
            elif event.type() == QEvent.Type.DragLeave:
                self.dragLeaveEvent(event)
            else:
                self.dropEvent(event)
            return True
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not self._accept_drag(event):
            return
        self._drag_depth += 1
        self._set_drag_active(True)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self._accept_drag(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._drag_depth = max(0, self._drag_depth - 1)
        if self._drag_depth == 0:
            self._set_drag_active(False)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._drag_depth = 0
        self._set_drag_active(False)
        if self._busy:
            event.ignore()
            return
        paths = _paths_from_drop(event)
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.files_dropped.emit(paths)
