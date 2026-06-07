"""Превью фото в формах (лауреат, член НК)."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QSizePolicy, QWidget


def make_photo_preview_label(width: int = 120, height: int = 150) -> QLabel:
    lbl = QLabel()
    lbl.setFixedSize(width, height)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setWordWrap(True)
    lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    lbl.setStyleSheet(
        "border: 1px solid #cfd4dc; border-radius: 4px; "
        "background-color: #f7f9fc; color: #666;"
    )
    set_photo_placeholder(lbl, "нет фото")
    return lbl


def bytes_to_pixmap(data: bytes | None, width: int, height: int) -> QPixmap | None:
    if not data:
        return None
    img = QImage()
    if not img.loadFromData(data):
        return None
    return QPixmap.fromImage(img).scaled(
        width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation,
    )


def set_photo_placeholder(label: QLabel, text: str = "нет фото") -> None:
    label.setPixmap(QPixmap())
    label.setText(text)


def set_photo_bytes(label: QLabel, data: bytes | None) -> None:
    w, h = label.width(), label.height()
    pm = bytes_to_pixmap(data, w, h)
    if pm is None or pm.isNull():
        set_photo_placeholder(label, "нет фото")
        return
    label.setText("")
    label.setPixmap(pm)


def wrap_photo_row(preview: QLabel, *extra_widgets: QWidget) -> QWidget:
    """Контейнер фиксированной высоты — строка формы не схлопывается под таблицу."""
    from PyQt5.QtWidgets import QHBoxLayout

    box = QWidget()
    box.setMinimumHeight(preview.height() + 8)
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(preview)
    for w in extra_widgets:
        row.addWidget(w)
    row.addStretch()
    return box
