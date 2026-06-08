from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(12)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)

    def add_stretch(self) -> None:
        self._layout.addStretch()


class SectionHeader(QWidget):
    def __init__(self, title: str, badge: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        row.addWidget(title_label)
        row.addStretch()
        self.badge = QLabel(badge)
        self.badge.setObjectName("Badge")
        self.badge.setVisible(bool(badge))
        row.addWidget(self.badge)

    def set_badge(self, text: str) -> None:
        self.badge.setText(text)
        self.badge.setVisible(bool(text))


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("PrimaryButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def secondary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("SecondaryButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def ghost_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("GhostButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def danger_ghost_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("DangerGhostButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def toggle_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("ToggleButton")
    button.setCheckable(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    return label


class TextFieldCard(QWidget):
    def __init__(
        self,
        label: str,
        placeholder: str = "",
        read_only: bool = False,
        min_height: int = 140,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(field_label(label))
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText(placeholder)
        self.editor.setReadOnly(read_only)
        self.editor.setMinimumHeight(min_height)
        layout.addWidget(self.editor)

    def text(self) -> str:
        return self.editor.toPlainText()

    def set_text(self, value: str) -> None:
        self.editor.setPlainText(value)

    def clear(self) -> None:
        self.editor.clear()


def copy_to_clipboard(text: str) -> None:
    if text:
        QGuiApplication.clipboard().setText(text)


def paste_from_clipboard() -> str:
    return QGuiApplication.clipboard().text()
