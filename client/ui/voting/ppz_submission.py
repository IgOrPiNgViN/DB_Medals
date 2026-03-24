from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QFormLayout, QMessageBox, QTextEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from api_client import APIError


class PPZSubmissionPage(QWidget):
    """PPZ submission page (Представление на награждение)."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._laureates: list[dict] = []
        self._build_ui()
        self._load_laureates()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Представление на награждение (ППЗ)")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        select_group = QGroupBox("Выбор лауреата")
        sg_layout = QFormLayout(select_group)

        self.laureate_combo = QComboBox()
        self.laureate_combo.currentIndexChanged.connect(self._on_laureate_changed)
        sg_layout.addRow("Список лауреатов (статус «На голосование»):", self.laureate_combo)
        root.addWidget(select_group)

        info_group = QGroupBox("Информация о лауреате")
        ig_layout = QVBoxLayout(info_group)
        self.info_display = QTextEdit()
        self.info_display.setReadOnly(True)
        self.info_display.setMaximumHeight(180)
        self.info_display.setPlaceholderText("Выберите лауреата для просмотра информации...")
        ig_layout.addWidget(self.info_display)
        root.addWidget(info_group)

        btn_row = QHBoxLayout()

        self.btn_generate = QPushButton("Сформировать представление")
        self.btn_generate.setMinimumWidth(220)
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

    def _load_laureates(self):
        self.laureate_combo.clear()
        self._laureates = []
        try:
            all_laureates = self.api.get_laureates()
            self._laureates = [
                la for la in all_laureates
                if la.get("status", "").lower() in ("на голосование", "на голосовании")
            ]
        except APIError:
            try:
                self._laureates = self.api.get_laureates()
            except APIError:
                self._laureates = []

        for la in self._laureates:
            display = la.get("full_name", la.get("name", f"ID {la['id']}"))
            self.laureate_combo.addItem(display, la["id"])

        if self._laureates:
            self._on_laureate_changed(0)

    def _on_laureate_changed(self, idx: int):
        self.info_display.clear()
        if idx < 0 or idx >= len(self._laureates):
            return
        la = self._laureates[idx]
        try:
            detail = self.api.get_laureate(la["id"])
        except APIError:
            detail = la

        lines = [
            f"ФИО: {detail.get('full_name', detail.get('name', '—'))}",
            f"Категория: {detail.get('category', '—')}",
            f"Организация: {detail.get('organization', '—')}",
            f"Должность: {detail.get('position', '—')}",
            f"Статус: {detail.get('status', '—')}",
            f"Награда: {detail.get('award_name', '—')}",
        ]
        self.info_display.setPlainText("\n".join(lines))

    # ── slots ────────────────────────────────────────────────────────────

    def _on_generate(self):
        laureate_id = self.laureate_combo.currentData()
        if laureate_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите лауреата.")
            return
        try:
            self.api.create_ppz_submission({"laureate_id": laureate_id})
            QMessageBox.information(self, "Успех", "Представление на награждение сформировано.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать представление:\n{e}")

    def _on_export_pdf(self):
        QMessageBox.information(self, "Экспорт", "Конвертация в PDF будет реализована позднее.")

    def _on_export_word(self):
        QMessageBox.information(self, "Экспорт", "Конвертация в Word будет реализована позднее.")

    def _on_print(self):
        QMessageBox.information(self, "Печать", "Функция печати будет реализована позднее.")
