"""Путь к иконке приложения (dev и PyInstaller)."""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtGui import QIcon


def _resources_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "resources"
    return Path(__file__).resolve().parent / "resources"


def load_app_icon() -> QIcon:
    res = _resources_dir()
    for name in ("app_icon.ico", "app_icon.png"):
        path = res / name
        if path.is_file():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    return QIcon()
