from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class DayCoverageCard(QFrame):
    clicked = Signal(str)

    def __init__(self, day: dict, selected: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._date = day["date"]
        self.setObjectName("DayCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_status(day, selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        header = QHBoxLayout()
        date_label = QLabel(self._date)
        date_label.setStyleSheet("font-weight: 700; font-size: 12px; background: transparent;")
        header.addWidget(date_label)
        header.addStretch()
        status = QLabel(day["status_label"])
        status.setObjectName(self._badge_object_name(day))
        header.addWidget(status)
        layout.addLayout(header)

        csv_day = day.get("csv_day")
        log_day = day.get("log_day") or {}
        if csv_day:
            min_time = (csv_day.get("minDateTime") or "")[11:19]
            max_time = (csv_day.get("maxDateTime") or "")[11:19]
            time_range = f" · {min_time}–{max_time}" if min_time and max_time else ""
            detail = QLabel(f"{int(csv_day.get('rowCount') or 0):,} rows{time_range}")
            detail.setObjectName("MutedLabel")
            detail.setStyleSheet("font-size: 11px;")
            layout.addWidget(detail)
        elif not (log_day.get("acs1") and log_day.get("acs2")):
            detail = QLabel("Missing ACS1 or ACS2 file")
            detail.setObjectName("MutedLabel")
            detail.setStyleSheet("font-size: 11px;")
            layout.addWidget(detail)

    def _badge_object_name(self, day: dict) -> str:
        if day.get("complete"):
            return "BadgeSuccess"
        if day.get("csv_day"):
            return "BadgeWarning"
        log_day = day.get("log_day") or {}
        if log_day.get("acs1") and log_day.get("acs2"):
            return "BadgeInfo"
        return "Badge"

    def _apply_status(self, day: dict, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        if day.get("complete"):
            status = "complete"
        elif day.get("csv_day"):
            status = "parsed"
        else:
            log_day = day.get("log_day") or {}
            status = "ready" if log_day.get("acs1") and log_day.get("acs2") else "default"
        self.setProperty("status", status)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._date)
        super().mousePressEvent(event)


class CoverageSidebar(QWidget):
    day_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CoveragePanel")
        self._days: list[dict] = []
        self._selected_date = ""
        self._expanded = True
        self._cards: list[DayCoverageCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(14, 14, 10, 10)
        self.title = QLabel("Coverage")
        self.title.setObjectName("CardTitle")
        header.addWidget(self.title)
        header.addStretch()
        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("‹")
        self.toggle_btn.setToolTip("Collapse panel")
        self.toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self.toggle_btn)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(10, 0, 10, 10)
        self.body_layout.setSpacing(8)
        self.body_layout.addStretch()
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, stretch=1)

        self.summary = QLabel("")
        self.summary.setObjectName("MutedLabel")
        self.summary.setWordWrap(True)
        self.summary.setContentsMargins(14, 0, 14, 14)
        root.addWidget(self.summary)

        self.setMinimumWidth(268)
        self.setMaximumWidth(268)

    def set_days(self, days: list[dict], summary_text: str) -> None:
        self._days = days
        self.summary.setText(summary_text)
        while self.body_layout.count() > 1:
            item = self.body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards = []
        for day in days:
            card = DayCoverageCard(day, selected=day["date"] == self._selected_date)
            card.clicked.connect(self._on_day_clicked)
            self.body_layout.insertWidget(self.body_layout.count() - 1, card)
            self._cards.append(card)

    def set_selected_date(self, date: str) -> None:
        self._selected_date = date
        for card in self._cards:
            card.set_selected(card._date == date)

    def _on_day_clicked(self, date: str) -> None:
        self._selected_date = date
        for card in self._cards:
            card.set_selected(card._date == date)
        self.day_selected.emit(date)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self.setMinimumWidth(268)
            self.setMaximumWidth(268)
            self.title.setVisible(True)
            self.scroll.setVisible(True)
            self.summary.setVisible(True)
            self.toggle_btn.setText("‹")
            self.toggle_btn.setToolTip("Collapse panel")
        else:
            self.setMinimumWidth(52)
            self.setMaximumWidth(52)
            self.title.setVisible(False)
            self.scroll.setVisible(False)
            self.summary.setVisible(False)
            self.toggle_btn.setText("›")
            self.toggle_btn.setToolTip("Show coverage panel")
