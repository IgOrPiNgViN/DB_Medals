"""Общие помощники для форм PyQt."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFormLayout, QLabel, QScrollArea, QWidget, QPushButton


def apply_button_class(btn: QPushButton, css_class: str) -> None:
    """Применить класс из styles.qss (после setProperty нужен repolish)."""
    btn.setProperty("class", css_class)
    style = btn.style()
    style.unpolish(btn)
    style.polish(btn)
    btn.update()


def make_form_label(text: str, min_width: int = 178) -> QLabel:
    lbl = QLabel(text)
    lbl.setMinimumWidth(min_width)
    lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return lbl


def configure_form(form: QFormLayout, *, label_width: int = 178, row_spacing: int = 10) -> None:
    form.setVerticalSpacing(row_spacing)
    form.setHorizontalSpacing(12)
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
    form.setRowWrapPolicy(QFormLayout.DontWrapRows)


def make_scroll_page(content: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(content)
    return scroll
