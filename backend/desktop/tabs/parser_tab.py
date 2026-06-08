from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QVBoxLayout, QWidget

from desktop.parsing_tools import (
    analyze_duplicates,
    format_duplicate_report,
    format_numbers,
    format_numbers_with_quotes,
    get_trimmed_lines,
)
from desktop.widgets.common import (
    Card,
    SectionHeader,
    TextFieldCard,
    copy_to_clipboard,
    danger_ghost_button,
    field_label,
    ghost_button,
    paste_from_clipboard,
    primary_button,
    toggle_button,
)


class ParserTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(16)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.addWidget(self._build_formatter_card(), stretch=1)
        columns.addWidget(self._build_duplicates_card(), stretch=1)
        root.addLayout(columns)

    def _build_formatter_card(self) -> Card:
        card = Card()
        self.formatter_header = SectionHeader("Number Formatter")
        card.add_widget(self.formatter_header)

        mode_row = QHBoxLayout()
        mode_row.addWidget(field_label("Output mode"))
        mode_row.addStretch()
        self.plain_toggle = toggle_button("Plain")
        self.quoted_toggle = toggle_button("Quoted SQL")
        self.plain_toggle.setChecked(True)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.plain_toggle)
        group.addButton(self.quoted_toggle)
        mode_row.addWidget(self.plain_toggle)
        mode_row.addWidget(self.quoted_toggle)
        card.add_layout(mode_row)

        self.formatter_input = TextFieldCard("Input", "One number per line", min_height=180)
        self.formatter_output = TextFieldCard("Output", read_only=True, min_height=120)
        card.add_widget(self.formatter_input)
        card.add_widget(self.formatter_output)

        format_btn = primary_button("Format")
        format_btn.clicked.connect(self._run_formatter)
        copy_btn = ghost_button("Copy")
        copy_btn.clicked.connect(lambda: copy_to_clipboard(self.formatter_output.text()))
        paste_btn = ghost_button("Paste")
        paste_btn.clicked.connect(self._paste_formatter)
        clear_btn = danger_ghost_button("Clear")
        clear_btn.clicked.connect(self._clear_formatter)

        actions = QHBoxLayout()
        actions.addWidget(format_btn)
        actions.addWidget(copy_btn)
        actions.addWidget(paste_btn)
        actions.addWidget(clear_btn)
        actions.addStretch()
        card.add_layout(actions)

        self.plain_toggle.toggled.connect(self._on_mode_changed)
        self.quoted_toggle.toggled.connect(self._on_mode_changed)
        self.formatter_input.editor.textChanged.connect(self._run_formatter)
        return card

    def _build_duplicates_card(self) -> Card:
        card = Card()
        self.duplicates_header = SectionHeader("Duplicate Checker")
        card.add_widget(self.duplicates_header)

        self.duplicates_input = TextFieldCard("Input", "One number per line", min_height=180)
        self.duplicates_output = TextFieldCard("Report", read_only=True, min_height=120)
        card.add_widget(self.duplicates_input)
        card.add_widget(self.duplicates_output)

        analyze_btn = primary_button("Analyze")
        analyze_btn.clicked.connect(self._run_duplicates)
        copy_btn = ghost_button("Copy report")
        copy_btn.clicked.connect(lambda: copy_to_clipboard(self.duplicates_output.text()))
        paste_btn = ghost_button("Paste")
        paste_btn.clicked.connect(self._paste_duplicates)
        clear_btn = danger_ghost_button("Clear")
        clear_btn.clicked.connect(self._clear_duplicates)

        actions = QHBoxLayout()
        actions.addWidget(analyze_btn)
        actions.addWidget(copy_btn)
        actions.addWidget(paste_btn)
        actions.addWidget(clear_btn)
        actions.addStretch()
        card.add_layout(actions)

        self.duplicates_input.editor.textChanged.connect(self._run_duplicates)
        return card

    def _on_mode_changed(self) -> None:
        self._run_formatter()

    def _run_formatter(self) -> None:
        value = self.formatter_input.text()
        lines = get_trimmed_lines(value)
        self.formatter_header.set_badge(f"{len(lines)} lines")
        if not lines:
            self.formatter_output.clear()
            return
        if self.quoted_toggle.isChecked():
            self.formatter_output.set_text(format_numbers_with_quotes(value))
        else:
            self.formatter_output.set_text(format_numbers(value))

    def _run_duplicates(self) -> None:
        value = self.duplicates_input.text()
        lines = get_trimmed_lines(value)
        self.duplicates_header.set_badge(f"{len(lines)} lines")
        if not lines:
            self.duplicates_output.clear()
            return
        self.duplicates_output.set_text(format_duplicate_report(analyze_duplicates(value)))

    def _paste_formatter(self) -> None:
        self.formatter_input.set_text(paste_from_clipboard())

    def _paste_duplicates(self) -> None:
        self.duplicates_input.set_text(paste_from_clipboard())

    def _clear_formatter(self) -> None:
        self.formatter_input.clear()
        self.formatter_output.clear()
        self.formatter_header.set_badge("")

    def _clear_duplicates(self) -> None:
        self.duplicates_input.clear()
        self.duplicates_output.clear()
        self.duplicates_header.set_badge("")
