from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
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
    build_day_tooltip,
)

ROLE_DATE = Qt.ItemDataRole.UserRole
ROLE_STATUS = Qt.ItemDataRole.UserRole + 1
PANEL_WIDTH = 284

STRIPE_COLORS = {
    STATUS_FAILED: "#f44336",
    STATUS_MISSING: "#f44336",
    STATUS_PARTIAL: "#ff9800",
    STATUS_PARSING: "#7c9cff",
}

STATUS_COLORS = {
    STATUS_PARSED: "#6b7280",
    STATUS_READY: "#29b6f6",
    STATUS_PARSING: "#7c9cff",
    STATUS_PARTIAL: "#ff9800",
    STATUS_MISSING: "#f44336",
    STATUS_FAILED: "#f44336",
}

TABLE_HEADERS = [
    ("", "Day status icon"),
    ("Date", "Log date"),
    ("Status", "Parse and coverage status"),
    ("ACS", "ACS1 / ACS2 log files: ● present, ○ missing"),
    ("Rows", "Parsed message count"),
]


def _day_sort_key(day: dict, column: int):
    if column in (0, 2):
        return day.get("status_sort", 99)
    if column == 1:
        return day.get("date", "")
    if column == 3:
        log_day = day.get("log_day") or {}
        return int(bool(log_day.get("acs1"))) + int(bool(log_day.get("acs2")))
    if column == 4:
        csv_day = day.get("csv_day")
        if not csv_day:
            return -1
        return int(csv_day.get("rowCount") or 0)
    return ""


class CoverageRowDelegate(QStyledItemDelegate):
    def __init__(self, table: QTableWidget) -> None:
        super().__init__(table)
        self._table = table

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:
        super().initStyleOption(option, index)
        option.textElideMode = Qt.TextElideMode.ElideNone

    def paint(self, painter, option: QStyleOptionViewItem, index) -> None:
        item = self._table.item(index.row(), 0)
        status = item.data(ROLE_STATUS) if item else ""
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        painter.save()
        if selected:
            painter.fillRect(option.rect, QColor(124, 156, 255, 20))

        if index.column() == 0:
            if selected:
                painter.fillRect(option.rect.left(), option.rect.top(), 2, option.rect.height(), QColor("#7c9cff"))
            elif status in STRIPE_COLORS:
                painter.fillRect(
                    option.rect.left(),
                    option.rect.top(),
                    2,
                    option.rect.height(),
                    QColor(STRIPE_COLORS[status]),
                )

        if status == STATUS_PARSED and not selected:
            painter.setOpacity(0.55)

        super().paint(painter, option, index)
        painter.restore()


class CoverageSidebar(QWidget):
    days_selected = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CoveragePanel")
        self._days: list[dict] = []
        self._selected_dates: list[str] = []
        self._expanded = True
        self._syncing = False
        self._sort_column: int | None = None
        self._sort_ascending = True

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("CoverageHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 8, 6, 8)

        self.title = QLabel("Coverage")
        self.title.setObjectName("CoverageTitle")
        header_layout.addWidget(self.title)
        header_layout.addStretch()
        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("‹")
        self.toggle_btn.setToolTip("Collapse panel")
        self.toggle_btn.clicked.connect(self._toggle)
        header_layout.addWidget(self.toggle_btn)
        root.addWidget(header)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("CoverageTable")
        self._refresh_header_labels()
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setAlternatingRowColors(False)
        self.table.setFrameShape(QTableWidget.Shape.NoFrame)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSortingEnabled(False)

        header_view = self.table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionsClickable(True)
        header_view.setFixedHeight(22)
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header_view.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_view.sectionClicked.connect(self._on_header_clicked)
        self.table.setColumnWidth(0, 18)
        self.table.setColumnWidth(2, 54)
        self.table.setColumnWidth(3, 22)
        self.table.setColumnWidth(4, 44)

        table_font = QFont("Segoe UI", 9)
        self.table.setFont(table_font)
        self.table.setItemDelegate(CoverageRowDelegate(self.table))
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        root.addWidget(self.table, stretch=1)

        self._apply_panel_width(expanded=True)

    def _refresh_header_labels(self) -> None:
        for column, (label, tooltip) in enumerate(TABLE_HEADERS):
            text = label
            if self._sort_column is not None and column == self._sort_column:
                text = f"{label} {'↑' if self._sort_ascending else '↓'}"
            header_item = QTableWidgetItem(text)
            header_item.setToolTip(tooltip)
            self.table.setHorizontalHeaderItem(column, header_item)

    def set_days(self, days: list[dict]) -> None:
        self._days = list(days)
        if self._sort_column is None:
            self._populate_table(self._days)
        else:
            self._apply_sort()

    def set_selected_dates(self, dates: list[str]) -> None:
        self._selected_dates = list(dates)
        self._syncing = True
        self.table.clearSelection()
        if dates:
            date_set = set(dates)
            first_row = None
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if not item:
                    continue
                day_date = item.data(ROLE_DATE)
                if day_date in date_set:
                    for column in range(self.table.columnCount()):
                        cell = self.table.item(row, column)
                        if cell:
                            cell.setSelected(True)
                    if first_row is None:
                        first_row = row
            if first_row is not None:
                anchor = self.table.item(first_row, 0)
                if anchor:
                    self.table.scrollToItem(anchor)
        self._syncing = False

    def selected_dates(self) -> list[str]:
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        dates: list[str] = []
        for row in rows:
            item = self.table.item(row, 0)
            if not item:
                continue
            day_date = item.data(ROLE_DATE)
            if isinstance(day_date, str):
                dates.append(day_date)
        return dates

    def _on_header_clicked(self, column: int) -> None:
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True
        self._refresh_header_labels()
        self._apply_sort()

    def _apply_sort(self) -> None:
        sort_column = self._sort_column
        if sort_column is None:
            self._populate_table(self._days)
            return
        reverse = not self._sort_ascending
        sorted_days = sorted(
            self._days,
            key=lambda day: _day_sort_key(day, sort_column),
            reverse=reverse,
        )
        self._populate_table(sorted_days)

    def _populate_table(self, days: list[dict]) -> None:
        self.table.setRowCount(len(days))
        for row_index, day in enumerate(days):
            status = day.get("status", "")
            tooltip = build_day_tooltip(day)
            row_count = day.get("row_count_text", "—")

            icon_item = QTableWidgetItem(day.get("status_icon", ""))
            icon_item.setData(ROLE_DATE, day["date"])
            icon_item.setData(ROLE_STATUS, status)
            icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_item.setToolTip(tooltip)

            date_item = QTableWidgetItem(day["date"])
            date_item.setData(ROLE_DATE, day["date"])
            date_item.setData(ROLE_STATUS, status)
            date_item.setToolTip(tooltip)

            status_item = QTableWidgetItem(day.get("status_text", ""))
            status_item.setData(ROLE_STATUS, status)
            status_item.setToolTip(tooltip)
            status_color = STATUS_COLORS.get(status, "#e8eaed")
            status_item.setForeground(QBrush(QColor(status_color)))

            acs_item = QTableWidgetItem(day.get("coverage_dots", ""))
            acs_item.setData(ROLE_STATUS, status)
            acs_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            acs_item.setToolTip(day.get("acs_tooltip", tooltip))

            rows_item = QTableWidgetItem(row_count)
            rows_item.setData(ROLE_STATUS, status)
            rows_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            rows_item.setToolTip(tooltip)

            for item in (icon_item, date_item, status_item, acs_item, rows_item):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            self.table.setItem(row_index, 0, icon_item)
            self.table.setItem(row_index, 1, date_item)
            self.table.setItem(row_index, 2, status_item)
            self.table.setItem(row_index, 3, acs_item)
            self.table.setItem(row_index, 4, rows_item)

        if self._selected_dates:
            self.set_selected_dates(self._selected_dates)

    def _on_selection_changed(self) -> None:
        if self._syncing:
            return
        dates = self.selected_dates()
        self._selected_dates = dates
        self.days_selected.emit(dates)

    def _apply_panel_width(self, *, expanded: bool) -> None:
        if expanded:
            self.setMinimumWidth(PANEL_WIDTH)
            self.setMaximumWidth(PANEL_WIDTH)
        else:
            self.setMinimumWidth(52)
            self.setMaximumWidth(52)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._apply_panel_width(expanded=True)
            self.title.setVisible(True)
            self.table.setVisible(True)
            self.toggle_btn.setText("‹")
            self.toggle_btn.setToolTip("Collapse panel")
        else:
            self._apply_panel_width(expanded=False)
            self.title.setVisible(False)
            self.table.setVisible(False)
            self.toggle_btn.setText("›")
            self.toggle_btn.setToolTip("Show coverage panel")
