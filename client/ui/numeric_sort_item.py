"""Ячейки таблицы с числовой сортировкой (Qt по умолчанию сортирует как строки)."""

from __future__ import annotations

from typing import Any

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidgetItem

# Не пересекаемся с Qt.UserRole, который часто хранит id записи в проекте.
_SORT_NUM_ROLE = Qt.UserRole + 401


def _parse_number_text(text: str) -> float | None:
    if text is None:
        return None
    t = str(text).strip().replace("\u00a0", " ").replace(" ", "")
    if not t or t in ("—", "-", "…"):
        return None
    t = t.replace("%", "")
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t and "." not in t:
        t = t.replace(",", ".")
    try:
        if "." in t:
            return float(t)
        return float(int(t, 10))
    except ValueError:
        return None


def item_numeric_sort_key(item: QTableWidgetItem) -> tuple[int, Any]:
    """0 — числовой ключ, 1 — строка (нижний регистр)."""
    if item is None:
        return (1, "")
    v = item.data(_SORT_NUM_ROLE)
    if v is not None:
        try:
            return (0, float(v))
        except (TypeError, ValueError):
            pass
    num = _parse_number_text(item.text())
    if num is not None:
        return (0, num)
    return (1, (item.text() or "").lower())


class NumericSortTableItem(QTableWidgetItem):
    """
    Отображение — обычная строка; при сортировке сравниваются числа (id, количество, %),
    а не лексикографический порядок «10» < «2».
    """

    def __init__(
        self,
        text: str = "",
        sort_value: Any = None,
        *,
        read_only: bool = True,
    ):
        super().__init__("" if text is None else str(text))
        if read_only:
            self.setFlags(self.flags() & ~Qt.ItemIsEditable)
        if sort_value is not None and not isinstance(sort_value, bool):
            try:
                self.setData(_SORT_NUM_ROLE, float(sort_value))
            except (TypeError, ValueError):
                pass

    def __lt__(self, other):
        if other is None:
            return False
        if not isinstance(other, QTableWidgetItem):
            return NotImplemented
        at, av = item_numeric_sort_key(self)
        bt, bv = item_numeric_sort_key(other)
        if at == 0 and bt == 0:
            return av < bv
        if at == 0:
            return True
        if bt == 0:
            return False
        return av < bv
