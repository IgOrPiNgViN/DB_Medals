import html as html_module
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QGroupBox, QFormLayout, QMessageBox,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from api_client import APIError
from ui.print_helpers import export_html_to_pdf, print_html


class ExtractPage(QWidget):
    """Protocol extract generation page."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._protocols: list[dict] = []
        self._la_links: list[dict] = []
        self._extracts: list[dict] = []
        self._build_ui()
        self._load_protocols()
        self._load_extracts_table()

    def refresh_data(self):
        self._load_protocols()
        self._load_extracts_table()

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
        form.addRow("Лауреат–награда:", self.laureate_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по ФИО/награде...")
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

        self.btn_word = QPushButton("Word (DOCX)…")
        self.btn_word.clicked.connect(self._on_export_docx)
        export_row.addWidget(self.btn_word)

        self.btn_print = QPushButton("Печать")
        self.btn_print.clicked.connect(self._on_print)
        export_row.addWidget(self.btn_print)

        export_row.addStretch()
        root.addLayout(export_row)

        list_group = QGroupBox("Сформированные выписки")
        lg = QVBoxLayout(list_group)
        self.extracts_table = QTableWidget()
        self.extracts_table.setColumnCount(4)
        self.extracts_table.setHorizontalHeaderLabels(
            ["ID", "Протокол", "Связка лауреат–награда", "Дата"],
        )
        self.extracts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.extracts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.extracts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.extracts_table.setMaximumHeight(180)
        lg.addWidget(self.extracts_table)
        ext_btns = QHBoxLayout()
        self.btn_delete_extract = QPushButton("Удалить выбранную выписку")
        self.btn_delete_extract.setProperty("class", "btn-danger")
        self.btn_delete_extract.clicked.connect(self._on_delete_extract)
        ext_btns.addWidget(self.btn_delete_extract)
        self.btn_refresh_extracts = QPushButton("Обновить")
        self.btn_refresh_extracts.clicked.connect(self.refresh_data)
        ext_btns.addWidget(self.btn_refresh_extracts)
        ext_btns.addStretch()
        lg.addLayout(ext_btns)
        root.addWidget(list_group)

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
        self._la_links = []
        try:
            grouped = self.api.report_awards_laureates()
            flat = []
            for award in grouped or []:
                for la in award.get("laureates") or []:
                    flat.append(la)
            self._la_links = flat
        except APIError:
            return
        self._fill_laureate_combo(self._la_links)

    def _fill_laureate_combo(self, items: list):
        self.laureate_combo.clear()
        for it in items:
            la_id = it.get("laureate_award_id")
            if la_id is None:
                continue
            name = it.get("full_name") or it.get("laureate_name") or ""
            award = it.get("award_name") or ""
            display = f"{name} — {award}".strip(" —")
            self.laureate_combo.addItem(display or f"Связка #{la_id}", la_id)

    def _on_search_changed(self, text: str):
        text_lower = text.strip().lower()
        if not text_lower:
            self._fill_laureate_combo(self._la_links)
            return
        filtered = [
            it for it in self._la_links
            if text_lower in (str(it.get("full_name") or it.get("laureate_name") or "") + " " + str(it.get("award_name") or "")).lower()
        ]
        self._fill_laureate_combo(filtered)

    # ── slots ────────────────────────────────────────────────────────────

    def _on_generate(self):
        proto_idx = self.protocol_combo.currentIndex()
        if proto_idx < 0 or proto_idx >= len(self._protocols):
            QMessageBox.warning(self, "Ошибка", "Выберите протокол.")
            return
        protocol_id = self._protocols[proto_idx]["id"]
        laureate_award_id = self.laureate_combo.currentData()
        if laureate_award_id is None:
            QMessageBox.warning(self, "Ошибка", "Выберите связку лауреат–награда.")
            return

        try:
            created = self.api.create_protocol_extract(
                protocol_id,
                {"protocol_id": protocol_id, "laureate_award_id": int(laureate_award_id)},
            )
            self._extracts.append(created)
            QMessageBox.information(self, "Успех", "Выписка сформирована. Можно скачать DOCX.")
            self._load_extracts_table()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать выписку:\n{e}")

    def _load_extracts_table(self):
        try:
            self._extracts = self.api.list_protocol_extracts()
        except APIError:
            self._extracts = []
        self.extracts_table.setRowCount(0)
        for i, ex in enumerate(self._extracts):
            self.extracts_table.insertRow(i)
            eid = int(ex["id"])
            id_item = QTableWidgetItem(str(eid))
            id_item.setData(Qt.UserRole, eid)
            self.extracts_table.setItem(i, 0, id_item)
            self.extracts_table.setItem(
                i, 1, QTableWidgetItem(str(ex.get("protocol_id", "—"))),
            )
            self.extracts_table.setItem(
                i, 2, QTableWidgetItem(str(ex.get("laureate_award_id", "—"))),
            )
            self.extracts_table.setItem(
                i, 3, QTableWidgetItem(str(ex.get("extract_date", "—"))),
            )

    def _on_delete_extract(self):
        rows = self.extracts_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Удаление", "Выберите выписку в таблице.")
            return
        it = self.extracts_table.item(rows[0].row(), 0)
        eid = it.data(Qt.UserRole) if it else None
        if eid is None:
            return
        answer = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Удалить выписку ID {eid}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.api.delete_protocol_extract(int(eid))
        except APIError as e:
            if e.status_code == 404:
                self._load_extracts_table()
                self._load_protocols()
                QMessageBox.information(
                    self,
                    "Удаление",
                    "Выписка уже удалена (например, вместе с бюллетенем/протоколом). "
                    "Список обновлён.",
                )
                return
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить выписку:\n{e.detail}")
            return
        self._load_extracts_table()

    def _build_extract_html(self) -> str:
        proto_idx = self.protocol_combo.currentIndex()
        if proto_idx < 0 or proto_idx >= len(self._protocols):
            return ""
        p = self._protocols[proto_idx]
        laureate_name = self.laureate_combo.currentText().strip()
        lines = [
            "<html><head><meta charset='utf-8'></head><body>",
            "<h2>Выписка из протокола</h2>",
            f"<p><b>Протокол:</b> №{html_module.escape(str(p.get('number', '—')))} "
            f"от {html_module.escape(str(p.get('date', '—')))}</p>",
            f"<p><b>Лауреат:</b> {html_module.escape(laureate_name or '—')}</p>",
            f"<p><i>Сформировано: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i></p>",
            "<p>Текст выписки подставляется после нажатия «Сформировать выписку» в базе; "
            "здесь выводятся выбранные параметры для печати и экспорта.</p>",
            "</body></html>",
        ]
        return "".join(lines)

    def _on_export_pdf(self):
        html = self._build_extract_html()
        if not html:
            QMessageBox.warning(self, "Экспорт", "Выберите протокол и лауреата.")
            return
        export_html_to_pdf(html, self, "выписка.pdf")

    def _on_export_docx(self):
        # Пытаемся найти существующую выписку (protocol_id + laureate_award_id)
        proto_idx = self.protocol_combo.currentIndex()
        if proto_idx < 0 or proto_idx >= len(self._protocols):
            QMessageBox.warning(self, "Word (DOCX)", "Выберите протокол.")
            return
        protocol_id = self._protocols[proto_idx]["id"]
        laureate_award_id = self.laureate_combo.currentData()
        if laureate_award_id is None:
            QMessageBox.warning(self, "Word (DOCX)", "Выберите связку лауреат–награда.")
            return

        try:
            extracts = self.api.list_protocol_extracts()
        except APIError:
            extracts = []
        extract_id = None
        for e in extracts or []:
            if e.get("protocol_id") == protocol_id and e.get("laureate_award_id") == int(laureate_award_id):
                extract_id = e.get("id")
                break
        if extract_id is None:
            QMessageBox.information(self, "Word (DOCX)", "Сначала нажмите «Сформировать выписку».")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить выписку (DOCX)",
            "выписка.docx",
            "Документ Word (*.docx);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            data = self.api.download_extract_docx(int(extract_id))
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Word (DOCX)", "Файл сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось скачать DOCX:\n{e}")

    def _on_print(self):
        html = self._build_extract_html()
        if not html:
            QMessageBox.warning(self, "Печать", "Выберите протокол и лауреата.")
            return
        print_html(html, self)
