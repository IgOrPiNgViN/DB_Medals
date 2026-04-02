from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QFormLayout, QMessageBox, QTextEdit, QFileDialog,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from api_client import APIError
from ui.print_helpers import export_html_to_pdf, print_html, plain_text_to_html


class PPZSubmissionPage(QWidget):
    """PPZ submission page (Представление на награждение)."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._la_links: list[dict] = []
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
        sg_layout.addRow("Лауреат–награда:", self.laureate_combo)
        root.addWidget(select_group)

        self.auth_combo = QComboBox()
        sg_layout.addRow("Уполномоченный (НК):", self.auth_combo)

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
        self.btn_word.setText("Word (DOCX)…")
        self.btn_word.clicked.connect(self._on_export_docx)
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
        self._la_links = []
        try:
            grouped = self.api.report_awards_laureates()
            flat = []
            for award in grouped or []:
                for la in award.get("laureates") or []:
                    flat.append(la)
            self._la_links = flat
        except APIError:
            self._la_links = []

        for it in self._la_links:
            la_id = it.get("laureate_award_id")
            if la_id is None:
                continue
            name = it.get("full_name") or it.get("laureate_name") or ""
            award = it.get("award_name") or ""
            display = f"{name} — {award}".strip(" —")
            self.laureate_combo.addItem(display or f"Связка #{la_id}", la_id)

        self.auth_combo.clear()
        try:
            members = self.api.get_committee_members(is_active=True)
        except APIError:
            members = []
        for m in members or []:
            self.auth_combo.addItem(m.get("full_name", f"#{m.get('id')}"), m.get("id"))

        if self._la_links:
            self._on_laureate_changed(0)

    def _on_laureate_changed(self, idx: int):
        self.info_display.clear()
        if idx < 0 or idx >= len(self._la_links):
            return
        la = self._la_links[idx]
        name = la.get("full_name") or la.get("laureate_name") or "—"
        award = la.get("award_name") or "—"
        lines = [
            f"Связка: #{la.get('laureate_award_id', '—')}",
            f"ФИО: {name}",
            f"Награда: {award}",
        ]
        self.info_display.setPlainText("\n".join(lines))

    # ── slots ────────────────────────────────────────────────────────────

    def _on_generate(self):
        laureate_award_id = self.laureate_combo.currentData()
        auth_id = self.auth_combo.currentData()
        if laureate_award_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите связку лауреат–награда.")
            return
        if auth_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите уполномоченного.")
            return
        try:
            created = self.api.create_ppz_submission(
                {"laureate_award_id": int(laureate_award_id), "authorized_member_id": int(auth_id)},
            )
            QMessageBox.information(
                self,
                "Успех",
                f"Представление сформировано (ID {created.get('id', '—')}). Можно скачать DOCX.",
            )
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать представление:\n{e}")

    def _build_document_html(self) -> str:
        body = self.info_display.toPlainText().strip()
        if not body:
            return ""
        title = (
            "Представление на награждение (ППЗ) — "
            f"{datetime.now().strftime('%d.%m.%Y')}"
        )
        extra = f"\n\n<i>Сформировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
        return plain_text_to_html(title, body + extra)

    def _on_export_pdf(self):
        html = self._build_document_html()
        if not html:
            QMessageBox.warning(self, "Экспорт", "Выберите лауреата с данными.")
            return
        export_html_to_pdf(html, self, "ППЗ.pdf")

    def _on_export_docx(self):
        laureate_award_id = self.laureate_combo.currentData()
        auth_id = self.auth_combo.currentData()
        if laureate_award_id is None or auth_id is None:
            QMessageBox.warning(self, "Word (DOCX)", "Выберите связку и уполномоченного.")
            return
        try:
            items = self.api.list_ppz_submissions()
        except APIError:
            items = []
        ppz_id = None
        for it in items or []:
            if it.get("laureate_award_id") == int(laureate_award_id) and it.get("authorized_member_id") == int(auth_id):
                ppz_id = it.get("id")
                break
        if ppz_id is None:
            QMessageBox.information(self, "Word (DOCX)", "Сначала нажмите «Сформировать представление».")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить представление ППЗ (DOCX)",
            "ППЗ.docx",
            "Документ Word (*.docx);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            data = self.api.download_ppz_submission_docx(int(ppz_id))
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Word (DOCX)", "Файл сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось скачать DOCX:\n{e}")

    def _on_print(self):
        html = self._build_document_html()
        if not html:
            QMessageBox.warning(self, "Печать", "Выберите лауреата с данными.")
            return
        print_html(html, self)
