from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QCheckBox, QTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView,
    QComboBox, QDialog, QDialogButtonBox, QGroupBox, QFileDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont

from api_client import APIError
from ui.numeric_sort_item import NumericSortTableItem
from ui.print_helpers import print_table
from ui.photo_helpers import make_photo_preview_label, set_photo_bytes, set_photo_placeholder, wrap_photo_row
from ui.table_fill import configure_table_rows
from ui.form_helpers import make_form_label, configure_form, make_scroll_page


class AddAwardDialog(QDialog):
    """Dialog to pick an award for signing/authorization assignment."""

    def __init__(self, awards: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор награды")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите награду:"))

        self.combo = QComboBox()
        self._award_ids: list[int] = []
        for a in awards:
            self.combo.addItem(a.get("name", f"Награда #{a['id']}"))
            self._award_ids.append(a["id"])
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_award_id(self) -> int | None:
        idx = self.combo.currentIndex()
        if 0 <= idx < len(self._award_ids):
            return self._award_ids[idx]
        return None


class MemberCardPage(QWidget):
    """Detail card for a single committee member."""

    back_requested = pyqtSignal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._member_id: int | None = None
        self._signing_data: list = []
        self._authorized_data: list = []
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(16)

        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("← Назад")
        self.btn_back.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(self.btn_back)
        self.btn_print = QPushButton("Печать карточки")
        self.btn_print.setProperty("class", "btn-secondary")
        self.btn_print.clicked.connect(self._on_print)
        top_bar.addWidget(self.btn_print)
        top_bar.addStretch()
        root.addLayout(top_bar)

        title = QLabel("Карточка члена НК")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        form_group = QGroupBox("Персональные данные")
        form = QFormLayout(form_group)
        configure_form(form)

        self.full_name_edit = QLineEdit()
        self.position_edit = QLineEdit()
        self.organization_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.phone_work_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.birth_date_edit = QLineEdit()
        self.birth_date_edit.setPlaceholderText("ГГГГ-ММ-ДД")
        self.assistant_name_edit = QLineEdit()
        self.assistant_phone_edit = QLineEdit()
        self.inclusion_number_edit = QLineEdit()
        self.inclusion_date_edit = QLineEdit()
        self.consent_letter_edit = QLineEdit()
        self.non_voting_check = QCheckBox("Неголосующий")
        self.active_check = QCheckBox("Действующий")
        self.notes_edit = QTextEdit()
        self.notes_edit.setMinimumHeight(72)
        self.notes_edit.setMaximumHeight(120)

        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.addWidget(self.active_check)
        status_layout.addWidget(self.non_voting_check)
        status_layout.addStretch()

        self.photo_label = make_photo_preview_label(120, 150)
        btn_photo = QPushButton("Загрузить фото…")
        btn_photo.clicked.connect(self._on_upload_photo)
        photo_widget = wrap_photo_row(self.photo_label, btn_photo)

        fl = make_form_label
        form.addRow(fl("ФИО:"), self.full_name_edit)
        form.addRow(fl("Должность:"), self.position_edit)
        form.addRow(fl("Организация:"), self.organization_edit)
        form.addRow(fl("Телефон (моб):"), self.phone_edit)
        form.addRow(fl("Телефон (раб):"), self.phone_work_edit)
        form.addRow(fl("Email:"), self.email_edit)
        form.addRow(fl("Дата рождения:"), self.birth_date_edit)
        form.addRow(fl("ФИО помощника:"), self.assistant_name_edit)
        form.addRow(fl("Тел. помощника:"), self.assistant_phone_edit)
        form.addRow(fl("Протокол вкл. №:"), self.inclusion_number_edit)
        form.addRow(fl("Протокол вкл. дата:"), self.inclusion_date_edit)
        form.addRow(fl("Письмо о согласии:"), self.consent_letter_edit)
        form.addRow(fl("Статус:"), status_row)
        form.addRow(fl("Примечания:"), self.notes_edit)
        form.addRow(fl("Фотография:"), photo_widget)
        root.addWidget(form_group)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.setMinimumWidth(140)
        self.btn_save.clicked.connect(self._on_save)
        save_row.addWidget(self.btn_save)
        root.addLayout(save_row)

        signing_group = QGroupBox("Подписант удостоверений следующих наград")
        sg_layout = QVBoxLayout(signing_group)

        self.signing_table = QTableWidget()
        self.signing_table.setColumnCount(2)
        self.signing_table.setHorizontalHeaderLabels(["№", "Награда"])
        self.signing_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.signing_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.signing_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.signing_table.setSortingEnabled(True)
        self.signing_table.horizontalHeader().setSortIndicatorShown(True)
        self.signing_table.verticalHeader().setVisible(False)
        self.signing_table.setMinimumHeight(100)
        configure_table_rows(self.signing_table, 36)
        sg_layout.addWidget(self.signing_table)

        sg_btns = QHBoxLayout()
        self.btn_add_signing = QPushButton("Добавить")
        self.btn_add_signing.clicked.connect(self._on_add_signing)
        sg_btns.addWidget(self.btn_add_signing)
        self.btn_remove_signing = QPushButton("Удалить")
        self.btn_remove_signing.clicked.connect(self._on_remove_signing)
        sg_btns.addWidget(self.btn_remove_signing)
        sg_btns.addStretch()
        sg_layout.addLayout(sg_btns)
        root.addWidget(signing_group)

        auth_group = QGroupBox("Уполномоченный по наградам")
        ag_layout = QVBoxLayout(auth_group)

        self.auth_table = QTableWidget()
        self.auth_table.setColumnCount(2)
        self.auth_table.setHorizontalHeaderLabels(["№", "Награда"])
        self.auth_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.auth_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.auth_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.auth_table.setSortingEnabled(True)
        self.auth_table.horizontalHeader().setSortIndicatorShown(True)
        self.auth_table.verticalHeader().setVisible(False)
        self.auth_table.setMinimumHeight(100)
        configure_table_rows(self.auth_table, 36)
        ag_layout.addWidget(self.auth_table)

        ag_btns = QHBoxLayout()
        self.btn_add_auth = QPushButton("Добавить")
        self.btn_add_auth.clicked.connect(self._on_add_auth)
        ag_btns.addWidget(self.btn_add_auth)
        self.btn_remove_auth = QPushButton("Удалить")
        self.btn_remove_auth.clicked.connect(self._on_remove_auth)
        ag_btns.addWidget(self.btn_remove_auth)
        ag_btns.addStretch()
        ag_layout.addLayout(ag_btns)
        root.addWidget(auth_group)

        root.addStretch()
        content.setMinimumWidth(640)
        outer.addWidget(make_scroll_page(content))

    # ── public API ───────────────────────────────────────────────────────

    def load_member(self, member_id: int):
        self._member_id = member_id
        try:
            data = self.api.get_committee_member(member_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные:\n{e}")
            return

        self.full_name_edit.setText(data.get("full_name", ""))
        self.position_edit.setText(data.get("position", ""))
        self.organization_edit.setText(data.get("organization", ""))
        self.phone_edit.setText(data.get("phone") or "")
        self.phone_work_edit.setText(data.get("phone_work") or "")
        self.email_edit.setText(data.get("email") or "")
        self.birth_date_edit.setText(str(data.get("birth_date") or ""))
        self.assistant_name_edit.setText(data.get("assistant_name") or "")
        self.assistant_phone_edit.setText(data.get("assistant_phone") or "")
        self.inclusion_number_edit.setText(data.get("inclusion_protocol_number") or "")
        self.inclusion_date_edit.setText(str(data.get("inclusion_protocol_date") or ""))
        self.consent_letter_edit.setText(data.get("consent_letter") or "")
        self.non_voting_check.setChecked(bool(data.get("is_non_voting")))
        self.active_check.setChecked(data.get("is_active", False))
        self.notes_edit.setPlainText(data.get("notes", ""))
        self._load_member_photo(bool(data.get("has_photo")))

        self._load_signing_rights()

    def _load_member_photo(self, has_photo: bool):
        if not has_photo or self._member_id is None:
            set_photo_placeholder(self.photo_label, "нет фото")
            return
        try:
            data = self.api.download_committee_member_photo(self._member_id)
            set_photo_bytes(self.photo_label, data)
        except APIError:
            set_photo_placeholder(self.photo_label, "есть фото")

    def _load_signing_rights(self):
        if self._member_id is None:
            return
        try:
            rights = self.api.get_signing_rights(self._member_id)
        except APIError:
            rights = []

        self._signing_data = [r for r in rights if r.get("role") == "signer"]
        self._authorized_data = [r for r in rights if r.get("role") == "authorized"]

        self._fill_rights_table(self.signing_table, self._signing_data)
        self._fill_rights_table(self.auth_table, self._authorized_data)

    @staticmethod
    def _fill_rights_table(table: QTableWidget, items: list):
        table.setSortingEnabled(False)
        table.setRowCount(0)
        for i, item in enumerate(items):
            table.insertRow(i)
            no = NumericSortTableItem(str(i + 1), i + 1)
            table.setItem(i, 0, no)
            name = item.get("award_name", f"Награда #{item.get('award_id', '?')}")
            name_it = QTableWidgetItem(name)
            name_it.setFlags(name_it.flags() & ~Qt.ItemIsEditable)
            rid = item.get("id")
            if rid is not None:
                name_it.setData(Qt.UserRole, int(rid))
            table.setItem(i, 1, name_it)
        table.setSortingEnabled(True)
        if items:
            table.setMinimumHeight(min(36 * len(items) + 42, 280))
        else:
            table.setMinimumHeight(100)

    # ── slots ────────────────────────────────────────────────────────────

    def _on_save(self):
        if self._member_id is None:
            return
        data = {
            "full_name": self.full_name_edit.text().strip(),
            "position": self.position_edit.text().strip(),
            "organization": self.organization_edit.text().strip(),
            "phone": self.phone_edit.text().strip() or None,
            "phone_work": self.phone_work_edit.text().strip() or None,
            "email": self.email_edit.text().strip() or None,
            "birth_date": self.birth_date_edit.text().strip() or None,
            "assistant_name": self.assistant_name_edit.text().strip() or None,
            "assistant_phone": self.assistant_phone_edit.text().strip() or None,
            "inclusion_protocol_number": self.inclusion_number_edit.text().strip() or None,
            "inclusion_protocol_date": self.inclusion_date_edit.text().strip() or None,
            "consent_letter": self.consent_letter_edit.text().strip() or None,
            "is_non_voting": self.non_voting_check.isChecked(),
            "is_active": self.active_check.isChecked(),
            "notes": self.notes_edit.toPlainText().strip(),
        }
        if not data["full_name"]:
            QMessageBox.warning(self, "Ошибка", "ФИО не может быть пустым.")
            return
        try:
            self.api.update_committee_member(self._member_id, data)
            QMessageBox.information(self, "Успех", "Данные сохранены.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e}")

    def _on_upload_photo(self):
        if self._member_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Фото члена НК", "", "Изображения (*.jpg *.jpeg *.png);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            self.api.upload_committee_member_photo(self._member_id, path)
            self._load_member_photo(True)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))

    def _fetch_awards(self) -> list:
        try:
            return self.api.get_awards()
        except APIError:
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить список наград.")
            return []

    def _on_add_signing(self):
        awards = self._fetch_awards()
        if not awards:
            return
        dlg = AddAwardDialog(awards, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        award_id = dlg.selected_award_id()
        if award_id is None:
            return
        try:
            self.api.assign_signing_right(self._member_id, {
                "member_id": self._member_id,
                "award_id": award_id,
                "role": "signer",
            })
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось назначить:\n{e}")
            return
        self._load_signing_rights()

    def _on_remove_signing(self):
        self._remove_selected_right(self.signing_table, self._signing_data)

    def _on_add_auth(self):
        awards = self._fetch_awards()
        if not awards:
            return
        dlg = AddAwardDialog(awards, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        award_id = dlg.selected_award_id()
        if award_id is None:
            return
        try:
            self.api.assign_signing_right(self._member_id, {
                "member_id": self._member_id,
                "award_id": award_id,
                "role": "authorized",
            })
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось назначить:\n{e}")
            return
        self._load_signing_rights()

    def _on_remove_auth(self):
        self._remove_selected_right(self.auth_table, self._authorized_data)

    def _remove_selected_right(self, table: QTableWidget, data_list: list):
        rows = table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Информация", "Выберите запись для удаления.")
            return
        row = rows[0].row()
        it = table.item(row, 1)
        right_id = it.data(Qt.UserRole) if it else None
        if right_id is None:
            return
        right_id = int(right_id)
        try:
            self.api.remove_signing_right(right_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e}")
            return
        self._load_signing_rights()

    def _on_print(self):
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Поле", "Значение"])
        rows = [
            ("ФИО", self.full_name_edit.text()),
            ("Должность", self.position_edit.text()),
            ("Организация", self.organization_edit.text()),
            ("Телефон (моб)", self.phone_edit.text()),
            ("Телефон (раб)", self.phone_work_edit.text()),
            ("Email", self.email_edit.text()),
            ("Дата рождения", self.birth_date_edit.text()),
            ("Помощник", self.assistant_name_edit.text()),
            ("Тел. помощника", self.assistant_phone_edit.text()),
            ("Протокол вкл. №", self.inclusion_number_edit.text()),
            ("Протокол вкл. дата", self.inclusion_date_edit.text()),
            ("Письмо о согласии", self.consent_letter_edit.text()),
            ("Действующий", "Да" if self.active_check.isChecked() else "Нет"),
            ("Примечания", self.notes_edit.toPlainText()),
        ]
        table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(k))
            table.setItem(i, 1, QTableWidgetItem(v))
        name = self.full_name_edit.text().strip() or "член НК"
        print_table(table, f"Карточка члена НК — {name}", self)

        for label, tbl in (("Подписант", self.signing_table), ("Уполномоченный", self.auth_table)):
            if tbl.rowCount() > 0:
                print_table(tbl, f"{name} — {label}", self)
