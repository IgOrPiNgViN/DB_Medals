"""Пакетное заполнение QTableWidget без блокировки UI."""

from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QSizePolicy, QTableWidget, QWidget,
)


def enable_table_sort_on_click(table: QTableWidget) -> None:
    """Включить сортировку только после клика по заголовку (быстрее для больших таблиц)."""
    header = table.horizontalHeader()
    if getattr(table, "_deferred_sort_installed", False):
        return
    table._deferred_sort_installed = True
    table.setSortingEnabled(False)

    def _on_click(section: int) -> None:
        if table.isSortingEnabled():
            return
        table.setSortingEnabled(True)
        header.setSortIndicator(section, header.sortIndicatorOrder())
        table.sortItems(section, header.sortIndicatorOrder())

    header.sectionClicked.connect(_on_click)


def configure_table_rows(table: QTableWidget, row_height: int = 36) -> None:
    """Единая высота строк — текст и виджеты в ячейках не обрезаются."""
    vh = table.verticalHeader()
    vh.setDefaultSectionSize(row_height)
    vh.setMinimumSectionSize(row_height)


def wrap_table_cell_widget(widget: QWidget) -> QWidget:
    """Обёртка для виджета в QTableWidget — без обрезания текста и рамок."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(3, 2, 3, 2)
    layout.setSpacing(0)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    widget.setProperty("class", "table-cell-widget")
    layout.addWidget(widget)
    container._table_cell_inner = widget  # type: ignore[attr-defined]
    return container


def table_cell_widget(table: QTableWidget, row: int, col: int) -> QWidget | None:
    """Виджет в ячейке (внутренний, если ячейка обёрнута)."""
    container = table.cellWidget(row, col)
    if container is None:
        return None
    inner = getattr(container, "_table_cell_inner", None)
    if inner is not None:
        return inner
    return container


def table_cell_combo_text(table: QTableWidget, row: int, col: int) -> str:
    w = table_cell_widget(table, row, col)
    if isinstance(w, QComboBox):
        return w.currentText()
    return ""


def fill_table_batched(
    table: QTableWidget,
    rows: list,
    fill_row: Callable[[QTableWidget, int, object], None],
    *,
    batch_size: int = 60,
    on_done: Callable[[], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    defer_sorting: bool = True,
) -> None:
    """Заполнить таблицу порциями через event loop."""
    table.setUpdatesEnabled(False)
    table.setSortingEnabled(False)
    table.setRowCount(len(rows))
    if not rows:
        if not defer_sorting:
            table.setSortingEnabled(True)
        table.setUpdatesEnabled(True)
        if on_done:
            on_done()
        return

    state = {"pos": 0}

    def step() -> None:
        if is_cancelled and is_cancelled():
            table.setUpdatesEnabled(True)
            return
        start = state["pos"]
        end = min(start + batch_size, len(rows))
        for row in range(start, end):
            fill_row(table, row, rows[row])
        state["pos"] = end
        if end < len(rows):
            QTimer.singleShot(0, step)
        else:
            if not defer_sorting:
                table.setSortingEnabled(True)
            table.setUpdatesEnabled(True)
            if on_done:
                on_done()

    QTimer.singleShot(0, step)
