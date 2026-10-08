from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPlainTextEdit, QVBoxLayout, QWidget


class LogViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImportContentFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.title_label = QLabel("Raw log")
        self.title_label.setObjectName("ImportPanelTitle")
        layout.addWidget(self.title_label)

        self.hint_label = QLabel("Select exactly one downloaded day to view its raw log.")
        self.hint_label.setObjectName("ImportMessage")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.text_frame = QFrame()
        self.text_frame.setObjectName("ImportContentArea")
        frame_layout = QVBoxLayout(self.text_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        self.text = QPlainTextEdit()
        self.text.setObjectName("ImportProgressList")
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        frame_layout.addWidget(self.text)
        layout.addWidget(self.text_frame, stretch=1)

        self.show_hint(self.hint_label.text())

    def show_hint(self, message: str) -> None:
        self.hint_label.setText(message)
        self.hint_label.setVisible(True)
        self.text_frame.setVisible(False)

    def show_content(self, date: str, content: str) -> None:
        self.title_label.setText(f"Raw log — {date}")
        self.hint_label.setVisible(False)
        self.text_frame.setVisible(True)
        self.text.setPlainText(content)
