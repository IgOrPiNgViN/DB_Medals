from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QGroupBox, QFormLayout, QMessageBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from api_client import APIError


class ExtractPage(QWidget):
    """Protocol extract generation page."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._protocols: list[dict] = []
        self._laureates: list[dict] = []
        self._build_ui()
        self._load_protocols()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Выписки из протоколов")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        form_group = QGroupBox("Параметры выписки")
        form = QFormLayout(form_group)

        self.protocol_combo = QComboBox()
        self.protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        form.addRow("Номер протокола:", self.protocol_combo)

        self.laureate_combo = QComboBox()
        form.addRow("Лауреат:", self.laureate_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по имени лауреата...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        form.addRow("Поиск:", self.search_edit)

        root.addWidget(form_group)

        btn_row = QHBoxLayout()

        self.btn_generate = QPushButton("Сформировать выписку")
        self.btn_generate.setMinimumWidth(180)
        self.btn_generate.clicked.connect(self._on_generate)
        btn_row.addWidget(self.btn_generate)

        btn_row.addStretch()
        root.addLayout(btn_row)

        export_row = QHBoxLayout()

        self.btn_pdf = QPushButton("Конвертировать в PDF")
        self.btn_pdf.clicked.connect(self._on_export_pdf)
        export_row.addWidget(self.btn_pdf)

        self.btn_word = QPushButton("Конвертировать в Word")
        self.btn_word.clicked.connect(self._on_export_word)
        export_row.addWidget(self.btn_word)

        self.btn_print = QPushButton("Печать")
        self.btn_print.clicked.connect(self._on_print)
        export_row.addWidget(self.btn_print)

        export_row.addStretch()
        root.addLayout(export_row)

        root.addStretch(1)

    # ── data ─────────────────────────────────────────────────────────────

    def _load_protocols(self):
        self.protocol_combo.blockSignals(True)
        self.protocol_combo.clear()
        try:
            self._protocols = self.api.get_protocols()
        except APIError:
            self._protocols = []

        for p in self._protocols:
            self.protocol_combo.addItem(
                f"Протокол №{p.get('number', '?')} от {p.get('date', '—')}",
                p["id"],
            )
        self.protocol_combo.blockSignals(False)
        if self._protocols:
            self._on_protocol_changed(0)

    def _on_protocol_changed(self, idx: int):
        self._load_laureates_for_protocol(idx)

    def _load_laureates_for_protocol(self, proto_idx: int):
        self.laureate_combo.clear()
        self._laureates = []
        try:
            laureates = self.api.get_laureates()
            self._laureates = laureates
        except APIError:
            return
        self._fill_laureate_combo(self._laureates)

    def _fill_laureate_combo(self, laureates: list):
        self.laureate_combo.clear()
        for la in laureates:
            display = la.get("full_name", la.get("name", f"ID {la['id']}"))
            self.laureate_combo.addItem(display, la["id"])

    def _on_search_changed(self, text: str):
        text_lower = text.strip().lower()
        if not text_lower:
            self._fill_laureate_combo(self._laureates)
            return
        filtered = [
            la for la in self._laureates
            if text_lower in la.get("full_name", la.get("name", "")).lower()
        ]
        self._fill_laureate_combo(filtered)

    # ── slots ────────────────────────────────────────────────────────────

    def _on_generate(self):
        proto_idx = self.protocol_combo.currentIndex()
        if proto_idx < 0 or proto_idx >= len(self._protocols):
            QMessageBox.warning(self, "Ошибка", "Выберите протокол.")
            return
        protocol_id = self._protocols[proto_idx]["id"]
        laureate_id = self.laureate_combo.currentData()
        if laureate_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите лауреата.")
            return

        try:
            self.api.create_protocol_extract(protocol_id, {"laureate_id": laureate_id})
            QMessageBox.information(self, "Успех", "Выписка сформирована.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать выписку:\n{e}")

    def _on_export_pdf(self):
        QMessageBox.information(self, "Экспорт", "Конвертация в PDF будет реализована позднее.")

    def _on_export_word(self):
        QMessageBox.information(self, "Экспорт", "Конвертация в Word будет реализована позднее.")

    def _on_print(self):
        QMessageBox.information(self, "Печать", "Функция печати будет реализована позднее.")
