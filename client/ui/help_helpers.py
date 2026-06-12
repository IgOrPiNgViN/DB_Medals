"""Кнопки «?» и показ справки по страницам и действиям."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from ui.form_helpers import apply_button_class


class HelpButton(QPushButton):
    """Маленькая чёрная «?» — по клику открывает инструкцию."""

    def __init__(self, help_text: str, title: str = "Справка", parent=None):
        super().__init__("?", parent)
        self._help_text = help_text.strip()
        self._title = title
        self.setFixedSize(20, 20)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Справка")
        self.setProperty("class", "help-btn")
        apply_button_class(self, "help-btn")
        self.clicked.connect(self._show)

    def _show(self) -> None:
        show_help(self, self._title, self._help_text)


def show_help(parent: QWidget | None, title: str, text: str) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(460, 280)
    root = QVBoxLayout(dlg)
    title_lbl = QLabel(title)
    title_lbl.setFont(QFont("Segoe UI", 12, QFont.Bold))
    root.addWidget(title_lbl)
    body = QTextEdit()
    body.setReadOnly(True)
    body.setPlainText(text.strip())
    body.setFont(QFont("Segoe UI", 10))
    root.addWidget(body, 1)
    btn = QPushButton("Закрыть")
    btn.clicked.connect(dlg.accept)
    row = QHBoxLayout()
    row.addStretch()
    row.addWidget(btn)
    root.addLayout(row)
    dlg.exec_()


def make_help_row(widget: QWidget, help_text: str, title: str = "Справка") -> QWidget:
    """Виджет (обычно кнопка) + «?» в одной строке."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(widget)
    layout.addWidget(HelpButton(help_text, title=title))
    return container
