"""Автоматическая установка справки «?» на страницах и кнопках."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QBoxLayout, QFormLayout, QGridLayout, QHBoxLayout, QLayout, QPushButton,
    QVBoxLayout, QWidget,
)

from ui.help_helpers import HelpButton
from ui.help_texts import button_help, page_help, page_title


_SKIP_CLASSES = frozenset({"help-btn", "sidebar-item"})


def install_help_for_page(page: QWidget, page_key: str) -> None:
    if page is None or getattr(page, "_help_installed", False):
        return
    page._help_installed = True  # type: ignore[attr-defined]

    text = page_help(page_key)
    title = page_title(page_key)
    _insert_page_help_bar(page, text, title)

    for btn in list(page.findChildren(QPushButton)):
        _wrap_button_if_needed(page_key, btn)


def _insert_page_help_bar(page: QWidget, text: str, title: str) -> None:
    layout = page.layout()
    if not isinstance(layout, QVBoxLayout):
        return
    bar = QWidget()
    bar.setProperty("class", "page-help-bar")
    row = QHBoxLayout(bar)
    row.setContentsMargins(0, 0, 0, 10)
    short = text.split("\n")[0]
    if len(short) > 140:
        short = short[:137] + "…"
    from PyQt5.QtWidgets import QLabel
    from PyQt5.QtGui import QFont

    hint = QLabel(short)
    hint.setWordWrap(True)
    hint.setFont(QFont("Segoe UI", 9))
    hint.setStyleSheet("color: #616161;")
    row.addWidget(hint, 1)
    row.addWidget(HelpButton(text, title=title))
    layout.insertWidget(0, bar)


def _should_skip_button(btn: QPushButton) -> bool:
    if btn.text().strip() == "?":
        return True
    if btn.property("_help_wrapped"):
        return True
    css = btn.property("class")
    if css in _SKIP_CLASSES:
        return True
    if isinstance(btn, HelpButton):
        return True
    parent = btn.parentWidget()
    while parent is not None:
        if parent.property("_help_row"):
            return True
        parent = parent.parentWidget()
    return False


def _wrap_button_if_needed(page_key: str, btn: QPushButton) -> None:
    if _should_skip_button(btn):
        return
    help_text = button_help(page_key, btn.text())
    title = page_title(page_key)
    if not _replace_in_layout(btn, help_text, title):
        return
    btn.setProperty("_help_wrapped", True)


def _replace_in_layout(btn: QPushButton, help_text: str, title: str) -> bool:
    parent = btn.parentWidget()
    if parent is None:
        return False
    layout = parent.layout()
    if layout is None:
        return False

    if isinstance(layout, (QHBoxLayout, QVBoxLayout, QBoxLayout)):
        idx = _box_index(layout, btn)
        if idx < 0:
            return False
        item = layout.takeAt(idx)
        if item is None:
            return False
        container = _make_help_row(btn, help_text, title)
        stretch = item.stretchFactor() if hasattr(item, "stretchFactor") else 0
        alignment = item.alignment() if hasattr(item, "alignment") else None
        layout.insertWidget(idx, container, stretch)
        if alignment is not None:
            layout.setAlignment(container, alignment)
        return True

    if isinstance(layout, QGridLayout):
        pos = _grid_position(layout, btn)
        if pos is None:
            return False
        row, col, rowspan, colspan = pos
        layout.removeWidget(btn)
        container = _make_help_row(btn, help_text, title)
        layout.addWidget(container, row, col, rowspan, colspan)
        return True

    return False


def _box_index(layout: QBoxLayout, widget: QWidget) -> int:
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item and item.widget() is widget:
            return i
    return -1


def _grid_position(layout: QGridLayout, widget: QWidget) -> tuple[int, int, int, int] | None:
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item and item.widget() is widget:
            return layout.getItemPosition(i)
    return None


def _make_help_row(btn: QPushButton, help_text: str, title: str) -> QWidget:
    container = QWidget()
    container.setProperty("_help_row", True)
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    row.addWidget(btn)
    row.addWidget(HelpButton(help_text, title=title))
    return container
