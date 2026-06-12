from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QFormLayout, QMessageBox, QTextEdit, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QStackedWidget,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from api_client import APIError
from ui.app_cache import AppCache
from ui.print_helpers import export_html_to_pdf, print_html, plain_text_to_html
from ui.table_fill import configure_table_rows
from ui.form_helpers import apply_button_class


class PPZSubmissionPage(QWidget):
    """PPZ submission page (Представление на награждение)."""

    assign_authorized_requested = pyqtSignal(int, str)

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._la_links: list[dict] = []
        self._ppz_items: list[dict] = []
        self._build_ui()
        self._load_laureates()
        self._load_ppz_table()

    def refresh_data(self):
        saved_la_id = self.laureate_combo.currentData()
        self._load_laureates(preserve_laureate_award_id=saved_la_id)
        self._load_ppz_table()

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

        self._auth_stack = QStackedWidget()
        self.auth_combo = QComboBox()
        self._auth_stack.addWidget(self.auth_combo)

        self._auth_empty_btn = QPushButton(
            "Уполномоченный не назначен — нажмите, чтобы перейти к назначению в НК",
        )
        self._auth_empty_btn.setCursor(Qt.PointingHandCursor)
        self._auth_empty_btn.setStyleSheet(
            "QPushButton { text-align: left; color: #1565C0; border: 1px dashed #90CAF9; "
            "border-radius: 4px; padding: 8px 10px; background: #E3F2FD; }"
            "QPushButton:hover { background: #BBDEFB; }",
        )
        self._auth_empty_btn.clicked.connect(self._on_assign_authorized_click)
        self._auth_stack.addWidget(self._auth_empty_btn)
        sg_layout.addRow("Уполномоченный (НК):", self._auth_stack)
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
        self.btn_word.setText("Word (DOCX)…")
        self.btn_word.clicked.connect(self._on_export_docx)
        export_row.addWidget(self.btn_word)

        self.btn_print = QPushButton("Печать")
        self.btn_print.clicked.connect(self._on_print)
        export_row.addWidget(self.btn_print)

        export_row.addStretch()
        root.addLayout(export_row)

        list_group = QGroupBox("Сформированные представления")
        lg = QVBoxLayout(list_group)
        self.ppz_table = QTableWidget()
        self.ppz_table.setColumnCount(4)
        self.ppz_table.setHorizontalHeaderLabels(
            ["ID", "Лауреат–награда", "Уполномоченный", "Дата"],
        )
        ppz_hdr = self.ppz_table.horizontalHeader()
        ppz_hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        ppz_hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        ppz_hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        ppz_hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        ppz_hdr.setStretchLastSection(False)
        ppz_hdr.setMinimumSectionSize(72)
        self.ppz_table.verticalHeader().setVisible(False)
        configure_table_rows(self.ppz_table, 36)
        self.ppz_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ppz_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.ppz_table.setMinimumHeight(160)
        lg.addWidget(self.ppz_table, 1)
        ppz_btns = QHBoxLayout()
        self.btn_delete_ppz = QPushButton("Удалить")
        apply_button_class(self.btn_delete_ppz, "btn-danger")
        self.btn_delete_ppz.clicked.connect(self._on_delete_ppz)
        ppz_btns.addWidget(self.btn_delete_ppz)
        ppz_btns.addStretch()
        lg.addLayout(ppz_btns)
        root.addWidget(list_group, 1)

    # ── data ─────────────────────────────────────────────────────────────

    def _load_laureates(self, preserve_laureate_award_id=None):
        self.laureate_combo.blockSignals(True)
        self.laureate_combo.clear()
        self.laureate_combo.blockSignals(False)
        self._la_links = []
        try:
            grouped = self.api.report_awards_laureates()
            flat = []
            for award in grouped or []:
                if (award.get("award_type") or "").lower() != "ppz":
                    continue
                for la in award.get("laureates") or []:
                    entry = dict(la)
                    entry["award_name"] = award.get("award_name")
                    entry["award_id"] = award.get("award_id")
                    entry["award_type"] = award.get("award_type")
                    flat.append(entry)
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

        if preserve_laureate_award_id is not None:
            saved = int(preserve_laureate_award_id)
            for i in range(self.laureate_combo.count()):
                data = self.laureate_combo.itemData(i)
                if data is not None and int(data) == saved:
                    self.laureate_combo.setCurrentIndex(i)
                    self._on_laureate_changed(i)
                    return

        if self._la_links:
            self._on_laureate_changed(0)
        else:
            self._reload_authorized_combo(None)

    def _reload_authorized_combo(self, award_id: int | None):
        self.auth_combo.clear()
        if award_id is None:
            self._auth_stack.setCurrentWidget(self._auth_empty_btn)
            return
        try:
            members = self.api.get_signers_for_award(int(award_id), role="authorized")
        except APIError:
            members = []
        for m in members or []:
            self.auth_combo.addItem(m.get("full_name", f"#{m.get('id')}"), m.get("id"))
        if members:
            self._auth_stack.setCurrentWidget(self.auth_combo)
        else:
            self._auth_stack.setCurrentWidget(self._auth_empty_btn)

    def _current_award_context(self) -> tuple[int | None, str]:
        idx = self.laureate_combo.currentIndex()
        if idx < 0 or idx >= len(self._la_links):
            return None, ""
        la = self._la_links[idx]
        award_id = la.get("award_id")
        award_name = la.get("award_name") or ""
        return (int(award_id) if award_id is not None else None), award_name

    def _on_assign_authorized_click(self):
        award_id, award_name = self._current_award_context()
        if award_id is None:
            QMessageBox.information(self, "Назначение", "Сначала выберите лауреата–награду (ППЗ).")
            return
        self.assign_authorized_requested.emit(award_id, award_name)

    def _laureate_link_label(self, laureate_award_id) -> str:
        try:
            la_id = int(laureate_award_id)
        except (TypeError, ValueError):
            return str(laureate_award_id)
        for it in self._la_links:
            if int(it.get("laureate_award_id") or -1) == la_id:
                name = it.get("full_name") or it.get("laureate_name") or "—"
                award = it.get("award_name") or "—"
                return f"{name} — {award}"
        return f"Связка #{la_id}"

    def _member_name(self, member_id) -> str:
        try:
            mid = int(member_id)
        except (TypeError, ValueError):
            return str(member_id)
        for m in AppCache.committee_members or []:
            if int(m.get("id") or -1) == mid:
                return m.get("full_name") or f"#{mid}"
        return f"#{mid}"

    def _on_laureate_changed(self, idx: int):
        self.info_display.clear()
        if idx < 0 or idx >= len(self._la_links):
            self._reload_authorized_combo(None)
            return
        la = self._la_links[idx]
        award_id = la.get("award_id")
        self._reload_authorized_combo(award_id)
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
            answer = QMessageBox.question(
                self,
                "Уполномоченный не назначен",
                "Для этой награды нет уполномоченного члена НК.\n\n"
                "Перейти к назначению?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                self._on_assign_authorized_click()
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
            self._load_ppz_table()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать представление:\n{e}")

    def _load_ppz_table(self):
        try:
            self._ppz_items = self.api.list_ppz_submissions()
        except APIError:
            self._ppz_items = []
        self.ppz_table.setRowCount(0)
        for i, item in enumerate(self._ppz_items):
            self.ppz_table.insertRow(i)
            pid = int(item["id"])
            id_item = QTableWidgetItem(str(pid))
            id_item.setData(Qt.UserRole, pid)
            self.ppz_table.setItem(i, 0, id_item)
            self.ppz_table.setItem(
                i, 1, QTableWidgetItem(self._laureate_link_label(item.get("laureate_award_id"))),
            )
            self.ppz_table.setItem(
                i, 2, QTableWidgetItem(self._member_name(item.get("authorized_member_id"))),
            )
            self.ppz_table.setItem(
                i, 3, QTableWidgetItem(str(item.get("submission_date", item.get("date", "—")))),
            )

    def _on_delete_ppz(self):
        rows = self.ppz_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Удаление", "Выберите представление в таблице.")
            return
        it = self.ppz_table.item(rows[0].row(), 0)
        ppz_id = it.data(Qt.UserRole) if it else None
        if ppz_id is None:
            return
        answer = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Удалить представление ППЗ ID {ppz_id}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.api.delete_ppz_submission(int(ppz_id))
        except APIError as e:
            if e.status_code == 404:
                self._load_ppz_table()
                QMessageBox.information(
                    self,
                    "Удаление",
                    "Запись уже удалена. Список обновлён.",
                )
                return
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить представление:\n{e.detail}")
            return
        self._load_ppz_table()

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
