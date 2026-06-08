from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from desktop.widgets.common import ghost_button, primary_button, secondary_button


class DayActionRow(QFrame):
    queue_clicked = Signal(dict)
    parse_clicked = Signal(dict)

    def __init__(self, day: dict, in_queue: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day = day
        self.setObjectName("DayActionRow")

        log_day = day.get("log_day") or {}
        has_pair = bool(log_day.get("acs1") and log_day.get("acs2"))
        status = day.get("status_label") or ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)
        date_label = QLabel(day["date"])
        date_label.setObjectName("CardTitle")
        left.addWidget(date_label)

        files = day.get("files") or []
        if files:
            names = QLabel(" · ".join(file.get("filename", "") for file in files[:2]))
            names.setObjectName("MutedLabel")
            names.setStyleSheet("font-size: 11px;")
            left.addWidget(names)
        layout.addLayout(left, stretch=2)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(self._chip("ACS1", bool(log_day.get("acs1"))))
        chips.addWidget(self._chip("ACS2", bool(log_day.get("acs2"))))
        layout.addLayout(chips)

        status_label = QLabel(status)
        status_label.setObjectName(self._status_badge(status))
        status_label.setFixedWidth(88)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label)

        self.queue_btn = secondary_button("Queued" if in_queue else "Queue")
        self.queue_btn.setEnabled(has_pair and not in_queue)
        self.queue_btn.clicked.connect(lambda: self.queue_clicked.emit(self._day))
        layout.addWidget(self.queue_btn)

        parse_label = "Re-parse" if day.get("csv_day") else "Parse"
        self.parse_btn = primary_button(parse_label)
        self.parse_btn.setEnabled(has_pair)
        self.parse_btn.clicked.connect(lambda: self.parse_clicked.emit(self._day))
        layout.addWidget(self.parse_btn)

    def _chip(self, label: str, present: bool) -> QLabel:
        chip = QLabel(label)
        chip.setObjectName("BadgeSuccess" if present else "Badge")
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setFixedWidth(52)
        return chip

    def _status_badge(self, status: str) -> str:
        lowered = status.lower()
        if lowered == "complete":
            return "BadgeSuccess"
        if lowered == "parsed":
            return "BadgeWarning"
        if lowered == "not parsed":
            return "BadgeInfo"
        return "Badge"
