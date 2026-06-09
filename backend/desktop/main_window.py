from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from desktop.tabs.logs_tab import LogsTab
from desktop.tabs.parser_tab import ParserTab
from desktop.theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VST Work Tools")
        self.setMinimumSize(1024, 700)

        shell = QWidget()
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("AppHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("VST Work Tools")
        title.setObjectName("AppTitle")
        header_layout.addWidget(title)
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(ParserTab(), "Parser")
        self.tabs.addTab(LogsTab(), "Logs")
        layout.addWidget(self.tabs, stretch=1)

        self.setCentralWidget(shell)


def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
