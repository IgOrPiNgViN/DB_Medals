"""Отчёт по перечню наград (как в Access: «об актуальных наградах»)."""

import html
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QComboBox,
    QMessageBox,
    QFileDialog,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

from api_client import APIClient, APIError

AWARD_TYPE_FILTER = [
    ("Все", None),
    ("Медали", "Медали"),
    ("ППЗ", "ППЗ"),
    ("Знаки отличия", "Знаки отличия"),
    ("Украшения", "Украшения"),
]

class CurrentAwardsReportPage(QWidget):
    """Перечень наград с датой отчёта — печать/PDF (полные строки без обрезки в форме)."""

    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        self.title_label = QLabel()
        self.title_label.setProperty("class", "page-title")
        layout.addWidget(self.title_label)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Тип награды:"))
        self.filter_combo = QComboBox()
        self.filter_combo.setMinimumWidth(200)
        for label, _ in AWARD_TYPE_FILTER:
            self.filter_combo.addItem(label)
        self.filter_combo.currentIndexChanged.connect(self.refresh_data)
        toolbar.addWidget(self.filter_combo)

        btn_refresh = QPushButton("Обновить")
        btn_refresh.clicked.connect(self.refresh_data)
        toolbar.addWidget(btn_refresh)

        toolbar.addStretch()

        btn_print = QPushButton("Печать")
        btn_print.clicked.connect(self._on_print)
        toolbar.addWidget(btn_print)

        btn_pdf = QPushButton("В PDF…")
        btn_pdf.setProperty("class", "btn-secondary")
        btn_pdf.clicked.connect(self._on_pdf)
        toolbar.addWidget(btn_pdf)

        layout.addLayout(toolbar)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text.setStyleSheet("font-family: 'Times New Roman', Times, serif; font-size: 12pt;")
        layout.addWidget(self.text, 1)

        hint = QLabel(
            "Список формируется из справочника наград на сервере. "
            "Для печати и PDF используются полные названия (без усечения, как в таблице на экране)."
        )
        hint.setWordWrap(True)
        hint.setProperty("class", "page-hint")
        layout.addWidget(hint)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_data()

    def refresh_data(self):
        _, type_value = AWARD_TYPE_FILTER[self.filter_combo.currentIndex()]
        try:
            awards = self.api.get_awards(award_type=type_value)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить награды.\n{e.detail}")
            awards = []

        awards = sorted(awards, key=lambda a: (a.get("name") or "").lower())
        today = QDate.currentDate().toString("dd.MM.yyyy")
        self.title_label.setText(f"Отчёт: об актуальных наградах {today}")

        parts = [
            "<html><body>",
            f'<p align="center"><b>Отчёт: об актуальных наградах {html.escape(today)}</b></p>',
            "<ol>",
        ]
        for a in awards:
            name = str(a.get("name") or "").strip()
            parts.append(f"<li>{html.escape(name)}</li>")
        parts.append("</ol></body></html>")
        self.text.setHtml("".join(parts))

    def _on_print(self):
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QPrintDialog.Accepted:
            self.text.document().print_(printer)

    def _on_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить отчёт в PDF",
            f"Актуальные_награды_{datetime.now().strftime('%Y-%m-%d')}.pdf",
            "PDF (*.pdf)",
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        self.text.document().print_(printer)
