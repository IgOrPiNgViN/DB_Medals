from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QFormLayout, QLineEdit, QDateEdit, QDialogButtonBox,
    QComboBox, QTextEdit, QGroupBox, QMessageBox, QCheckBox, QScrollArea, QFileDialog,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont

import html as html_module

from api_client import APIError
from ui.print_helpers import export_html_for_word, export_html_to_pdf, print_html


class CreateBulletinDialog(QDialog):
    """Dialog for creating a new bulletin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создать бюллетень")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.number_edit = QLineEdit()
        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate.currentDate().addDays(14))
        self.end_date.setCalendarPopup(True)
        self.address_edit = QLineEdit()

        layout.addRow("Номер бюллетеня:", self.number_edit)
        layout.addRow("Дата начала:", self.start_date)
        layout.addRow("Дата окончания:", self.end_date)
        layout.addRow("Почтовый адрес:", self.address_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> dict:
        return {
            "number": self.number_edit.text().strip(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "postal_address": self.address_edit.text().strip(),
        }


class DistributionDialog(QDialog):
    """Dialog to select NK members for bulletin distribution."""

    def __init__(self, members: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Рассылка бюллетеня")
        self.setMinimumSize(480, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите членов НК для рассылки:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._check_layout = QVBoxLayout(container)

        self._checkboxes: list[tuple[int, QCheckBox]] = []
        for m in members:
            cb = QCheckBox(m.get("full_name", f"ID {m['id']}"))
            cb.setChecked(True)
            self._check_layout.addWidget(cb)
            self._checkboxes.append((m["id"], cb))
        self._check_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_all = QPushButton("Выбрать всех")
        btn_all.clicked.connect(lambda: self._set_all(True))
        btn_row.addWidget(btn_all)
        btn_none = QPushButton("Снять всех")
        btn_none.clicked.connect(lambda: self._set_all(False))
        btn_row.addWidget(btn_none)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all(self, checked: bool):
        for _, cb in self._checkboxes:
            cb.setChecked(checked)

    def selected_member_ids(self) -> list[int]:
        return [mid for mid, cb in self._checkboxes if cb.isChecked()]


class BulletinPage(QWidget):
    """Bulletin creation and management page."""

    SECTIONS = ["Учреждение наград и НК", "Награждение лауреатов"]

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._bulletins: list[dict] = []
        self._current_bulletin_id: int | None = None
        self._last_doc_html: str = ""
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Бюллетени")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        top_row = QHBoxLayout()
        self.btn_create = QPushButton("Создать бюллетень")
        self.btn_create.clicked.connect(self._on_create)
        top_row.addWidget(self.btn_create)
        top_row.addStretch()
        root.addLayout(top_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["№", "Номер", "Дата начала", "Дата окончания"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_bulletin_selected)
        root.addWidget(self.table)

        # ── section editing area (shown after selecting a bulletin) ──────
        self.section_group = QGroupBox("Содержание бюллетеня")
        sg_layout = QVBoxLayout(self.section_group)

        sec_row = QHBoxLayout()
        sec_row.addWidget(QLabel("Раздел:"))
        self.section_combo = QComboBox()
        self.section_combo.addItems(self.SECTIONS)
        self.section_combo.currentIndexChanged.connect(self._on_section_changed)
        sec_row.addWidget(self.section_combo, 1)
        sg_layout.addLayout(sec_row)

        # Section 1: manual question
        self.question_widget = QWidget()
        q_layout = QVBoxLayout(self.question_widget)
        q_layout.setContentsMargins(0, 8, 0, 0)
        q_layout.addWidget(QLabel("Текст вопроса:"))
        self.question_edit = QTextEdit()
        self.question_edit.setMaximumHeight(100)
        q_layout.addWidget(self.question_edit)
        self.btn_save_question = QPushButton("Сохранить вопрос")
        self.btn_save_question.clicked.connect(self._on_save_question)
        q_layout.addWidget(self.btn_save_question, alignment=Qt.AlignLeft)
        sg_layout.addWidget(self.question_widget)

        # Section 2: laureate selection
        self.laureate_widget = QWidget()
        l_layout = QFormLayout(self.laureate_widget)
        l_layout.setContentsMargins(0, 8, 0, 0)
        self.laureate_section_hint = QLabel(
            "Показываются связки «лауреат–награда», у которых в карточке указан "
            "тот же номер бюллетеня, что у выбранного бюллетеня.",
        )
        self.laureate_section_hint.setWordWrap(True)
        l_layout.addRow(self.laureate_section_hint)
        self.laureate_combo = QComboBox()
        l_layout.addRow("Кандидат (связка):", self.laureate_combo)
        self.initiator_combo = QComboBox()
        l_layout.addRow("Инициатор (член НК):", self.initiator_combo)
        self.btn_save_laureate_q = QPushButton("Добавить вопрос в бюллетень")
        self.btn_save_laureate_q.clicked.connect(self._on_save_laureate_question)
        l_layout.addRow(self.btn_save_laureate_q)
        sg_layout.addWidget(self.laureate_widget)
        self.laureate_widget.setVisible(False)

        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("Сформировать бюллетень")
        self.btn_generate.clicked.connect(self._on_generate)
        btn_row.addWidget(self.btn_generate)

        self.btn_distribute = QPushButton("Рассылка")
        self.btn_distribute.clicked.connect(self._on_distribute)
        btn_row.addWidget(self.btn_distribute)

        self.btn_export_dist = QPushButton("Экспорт рассылки (CSV)…")
        self.btn_export_dist.setProperty("class", "btn-secondary")
        self.btn_export_dist.clicked.connect(self._on_export_distribution)
        btn_row.addWidget(self.btn_export_dist)

        self.btn_export_dist_xlsx = QPushButton("Экспорт рассылки (XLSX)…")
        self.btn_export_dist_xlsx.setProperty("class", "btn-secondary")
        self.btn_export_dist_xlsx.clicked.connect(self._on_export_distribution_xlsx)
        btn_row.addWidget(self.btn_export_dist_xlsx)
        btn_row.addStretch()
        sg_layout.addLayout(btn_row)

        doc_row = QHBoxLayout()
        self.btn_print_doc = QPushButton("Печать документа")
        self.btn_print_doc.clicked.connect(self._on_print_document)
        doc_row.addWidget(self.btn_print_doc)
        self.btn_pdf_doc = QPushButton("В PDF…")
        self.btn_pdf_doc.setProperty("class", "btn-secondary")
        self.btn_pdf_doc.clicked.connect(self._on_pdf_document)
        doc_row.addWidget(self.btn_pdf_doc)
        self.btn_word_doc = QPushButton("Для Word (HTML)")
        self.btn_word_doc.setProperty("class", "btn-secondary")
        self.btn_word_doc.clicked.connect(self._on_word_document)
        doc_row.addWidget(self.btn_word_doc)

        self.btn_docx = QPushButton("Word (DOCX)…")
        self.btn_docx.setProperty("class", "btn-secondary")
        self.btn_docx.clicked.connect(self._on_docx_document)
        doc_row.addWidget(self.btn_docx)
        doc_row.addStretch()
        sg_layout.addLayout(doc_row)

        self.section_group.setVisible(False)
        root.addWidget(self.section_group)

    # ── data ─────────────────────────────────────────────────────────────

    def load_data(self):
        try:
            self._bulletins = self.api.get_bulletins()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить бюллетени:\n{e}")
            self._bulletins = []

        self.table.setRowCount(0)
        for i, b in enumerate(self._bulletins):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(b.get("number", "")))
            vs = b.get("voting_start") or b.get("start_date")
            ve = b.get("voting_end") or b.get("end_date")
            self.table.setItem(i, 2, QTableWidgetItem(str(vs or "")))
            self.table.setItem(i, 3, QTableWidgetItem(str(ve or "")))

    # ── slots ────────────────────────────────────────────────────────────

    def _on_create(self):
        dlg = CreateBulletinDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        data = dlg.get_data()
        if not data["number"]:
            QMessageBox.warning(self, "Ошибка", "Номер бюллетеня не может быть пустым.")
            return
        try:
            self.api.create_bulletin(data)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать бюллетень:\n{e}")
            return
        self.load_data()

    def _on_bulletin_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.section_group.setVisible(False)
            self._current_bulletin_id = None
            return
        row = rows[0].row()
        if 0 <= row < len(self._bulletins):
            self._current_bulletin_id = self._bulletins[row]["id"]
            self.section_group.setVisible(True)
            self._on_section_changed(self.section_combo.currentIndex())

    def _on_section_changed(self, idx: int):
        is_section1 = idx == 0
        self.question_widget.setVisible(is_section1)
        self.laureate_widget.setVisible(not is_section1)

        if not is_section1:
            self._load_laureates()

    def _current_bulletin_number(self) -> str | None:
        if self._current_bulletin_id is None:
            return None
        for b in self._bulletins:
            if b.get("id") == self._current_bulletin_id:
                n = (b.get("number") or "").strip()
                return n or None
        return None

    def _load_laureates(self):
        self.laureate_combo.clear()
        self.initiator_combo.clear()
        bn = self._current_bulletin_number()
        if not bn:
            self.laureate_section_hint.setText("Сначала выберите бюллетень в таблице.")
            return
        self.laureate_section_hint.setText(
            f"Номер бюллетеня «{bn}». Связки подтягиваются из карточек лауреатов (кнопка «Связать награду»).",
        )
        try:
            rows = self.api.get_laureate_awards_by_bulletin_number(bn)
            for r in rows:
                la_id = r.get("laureate_award_id")
                if la_id is None:
                    continue
                fn = r.get("full_name") or "—"
                an = r.get("award_name") or "—"
                self.laureate_combo.addItem(f"{fn} — {an}", int(la_id))
            if self.laureate_combo.count() == 0:
                self.laureate_combo.addItem("— нет связок с этим номером —", None)
        except APIError:
            self.laureate_combo.addItem("— ошибка загрузки —", None)
        try:
            members = self.api.get_committee_members(is_active=True)
            for m in members:
                self.initiator_combo.addItem(m.get("full_name", f"ID {m['id']}"), m["id"])
        except APIError:
            pass

    def _on_save_question(self):
        if self._current_bulletin_id is None:
            return
        text = self.question_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Введите текст вопроса.")
            return
        try:
            full = self.api.get_bulletin_full(self._current_bulletin_id)
            section_id = None
            for s in full.get("sections", []):
                if s.get("section_name") == self.SECTIONS[0]:
                    section_id = s["id"]
                    break
            if section_id is None:
                sec = self.api.add_bulletin_section(
                    self._current_bulletin_id,
                    {
                        "bulletin_id": self._current_bulletin_id,
                        "section_name": self.SECTIONS[0],
                        "section_order": 0,
                    },
                )
                section_id = sec["id"]
                order = 0
            else:
                order = 0
                for s in full.get("sections", []):
                    if s.get("id") == section_id:
                        order = len(s.get("questions") or [])
                        break
            self.api.add_section_question(
                section_id,
                {
                    "section_id": section_id,
                    "question_text": text,
                    "question_order": order,
                },
            )
            QMessageBox.information(self, "Успех", "Вопрос сохранён.")
            self.question_edit.clear()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить вопрос:\n{e}")

    def _on_save_laureate_question(self):
        if self._current_bulletin_id is None:
            return
        la_id = self.laureate_combo.currentData()
        if la_id is None:
            QMessageBox.warning(
                self,
                "Вопрос",
                "Нет выбранной связки лауреат–награда с этим номером бюллетеня.\n"
                "Укажите номер при привязке награды к лауреату (карточки лауреатов).",
            )
            return
        initiator_name = ""
        ic = self.initiator_combo
        if ic.currentIndex() >= 0:
            initiator_name = ic.currentText().strip()
        try:
            ctx = self.api.get_laureate_award_context(int(la_id))
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить связку:\n{e}")
            return
        fn = ctx.get("full_name") or "—"
        an = ctx.get("award_name") or "—"
        qtext = (
            f"Награждение: {fn}. Награда: {an}."
            + (f" Инициатор: {initiator_name}." if initiator_name else "")
        )
        try:
            full = self.api.get_bulletin_full(self._current_bulletin_id)
            section_id = None
            for s in full.get("sections", []):
                if s.get("section_name") == self.SECTIONS[1]:
                    section_id = s["id"]
                    break
            if section_id is None:
                sec = self.api.add_bulletin_section(
                    self._current_bulletin_id,
                    {
                        "bulletin_id": self._current_bulletin_id,
                        "section_name": self.SECTIONS[1],
                        "section_order": 1,
                    },
                )
                section_id = sec["id"]
                order = 0
            else:
                order = 0
                for s in full.get("sections", []):
                    if s.get("id") == section_id:
                        order = len(s.get("questions") or [])
                        break
            self.api.add_section_question(
                section_id,
                {
                    "section_id": section_id,
                    "question_text": qtext,
                    "question_order": order,
                    "laureate_award_id": int(la_id),
                    "initiator": initiator_name or None,
                },
            )
            QMessageBox.information(self, "Успех", "Вопрос по кандидату добавлен в раздел «Награждение лауреатов».")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить вопрос:\n{e}")

    def _build_bulletin_html(self) -> str:
        if self._current_bulletin_id is None:
            return ""
        try:
            data = self.api.get_bulletin_full(self._current_bulletin_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить бюллетень:\n{e}")
            return ""
        parts = [
            "<html><head><meta charset='utf-8'></head><body>",
            f"<h1>Бюллетень голосования № {html_module.escape(str(data.get('number', '?')))}</h1>",
            f"<p>Период голосования: {html_module.escape(str(data.get('voting_start', '—')))} — "
            f"{html_module.escape(str(data.get('voting_end', '—')))}</p>",
            f"<p>Адрес: {html_module.escape(str(data.get('postal_address') or '—'))}</p>",
        ]
        secs = data.get("sections") or []
        if not secs:
            parts.append("<p><i>Вопросы не добавлены. Сохраните вопросы в разделе «Учреждение наград и НК».</i></p>")
        for sec in secs:
            parts.append(f"<h2>{html_module.escape(sec.get('section_name', ''))}</h2><ol>")
            for q in sec.get("questions") or []:
                qt = q.get("question_text", "")
                parts.append(f"<li>{html_module.escape(qt)}</li>")
            parts.append("</ol>")
        parts.append("</body></html>")
        return "".join(parts)

    def _on_generate(self):
        if self._current_bulletin_id is None:
            QMessageBox.warning(self, "Формирование", "Выберите бюллетень в таблице.")
            return
        self._last_doc_html = self._build_bulletin_html()
        if not self._last_doc_html:
            return
        QMessageBox.information(
            self, "Формирование",
            "Текст бюллетеня подготовлен. Используйте «Печать документа», «В PDF» или «Для Word».",
        )

    def _on_print_document(self):
        if not self._last_doc_html:
            self._last_doc_html = self._build_bulletin_html()
        if not self._last_doc_html:
            return
        print_html(self._last_doc_html, self)

    def _on_pdf_document(self):
        if not self._last_doc_html:
            self._last_doc_html = self._build_bulletin_html()
        if not self._last_doc_html:
            return
        export_html_to_pdf(self._last_doc_html, self, "бюллетень.pdf")

    def _on_word_document(self):
        if not self._last_doc_html:
            self._last_doc_html = self._build_bulletin_html()
        if not self._last_doc_html:
            return
        export_html_for_word(self._last_doc_html, self, "бюллетень.html")

    def _on_docx_document(self):
        if self._current_bulletin_id is None:
            QMessageBox.information(self, "Word (DOCX)", "Выберите бюллетень в таблице.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить бюллетень (DOCX)",
            "бюллетень.docx",
            "Документ Word (*.docx);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            data = self.api.download_bulletin_docx(self._current_bulletin_id)
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Word (DOCX)", "Файл сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать DOCX:\n{e}")

    def _on_distribute(self):
        if self._current_bulletin_id is None:
            return
        try:
            members = self.api.get_committee_members(is_active=True)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список НК:\n{e}")
            return
        if not members:
            QMessageBox.information(self, "Информация", "Нет действующих членов НК.")
            return

        dlg = DistributionDialog(members, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        selected = dlg.selected_member_ids()
        if not selected:
            QMessageBox.warning(self, "Предупреждение", "Не выбран ни один член НК.")
            return
        try:
            self.api.distribute_bulletin(self._current_bulletin_id, selected)
            QMessageBox.information(self, "Успех", f"Бюллетень разослан {len(selected)} членам НК.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка рассылки:\n{e}")

    def _on_export_distribution(self):
        if self._current_bulletin_id is None:
            QMessageBox.information(self, "Экспорт", "Выберите бюллетень в таблице.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить экспорт рассылки",
            f"bulletin_{self._current_bulletin_id}_distributions.csv",
            "CSV (*.csv);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            data = self.api.export_bulletin_distributions_csv(self._current_bulletin_id)
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Экспорт", "CSV сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось выгрузить CSV:\n{e}")

    def _on_export_distribution_xlsx(self):
        if self._current_bulletin_id is None:
            QMessageBox.information(self, "Экспорт", "Выберите бюллетень в таблице.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить экспорт рассылки (XLSX)",
            f"bulletin_{self._current_bulletin_id}_distributions.xlsx",
            "Excel (*.xlsx);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            data = self.api.export_bulletin_distributions_xlsx(self._current_bulletin_id)
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Экспорт", "XLSX сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось выгрузить XLSX:\n{e}")
