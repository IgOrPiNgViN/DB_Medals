"""Настройки QTabWidget: полный текст вкладок без обрезки."""

from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtCore import Qt


def configure_tab_bar_no_clip(tab_widget: QTabWidget) -> None:
    """Ширина вкладок по содержимому; при нехватке места — кнопки прокрутки."""
    bar = tab_widget.tabBar()
    bar.setExpanding(False)
    bar.setUsesScrollButtons(True)
    bar.setElideMode(Qt.ElideNone)
