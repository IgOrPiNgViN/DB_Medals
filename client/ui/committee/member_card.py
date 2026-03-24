from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QCheckBox, QTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView,
    QComboBox, QDialog, QDialogButtonBox, QGroupBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont

from api_client import APIError


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
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)

        top_bar = QHBoxLayout()
        self.btn_back = QPushButton("← Назад")
        self.btn_back.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(self.btn_back)
        top_bar.addStretch()
        root.addLayout(top_bar)

        title = QLabel("Карточка члена НК")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        form_group = QGroupBox("Персональные данные")
        form = QFormLayout(form_group)

        self.full_name_edit = QLineEdit()
        self.position_edit = QLineEdit()
        self.organization_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.active_check = QCheckBox("Действующий")
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)

        form.addRow("ФИО:", self.full_name_edit)
        form.addRow("Должность:", self.position_edit)
        form.addRow("Организация:", self.organization_edit)
        form.addRow("Телефон:", self.phone_edit)
        form.addRow("Email:", self.email_edit)
        form.addRow("Статус:", self.active_check)
        form.addRow("Примечания:", self.notes_edit)
        root.addWidget(form_group)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.setMinimumWidth(140)
        self.btn_save.clicked.connect(self._on_save)
        save_row.addWidget(self.btn_save)
        root.addLayout(save_row)

        # ── signing rights table ────────────────────────────────────────
        signing_group = QGroupBox("Подписант удостоверений следующих наград")
        sg_layout = QVBoxLayout(signing_group)

        self.signing_table = QTableWidget()
        self.signing_table.setColumnCount(2)
        self.signing_table.setHorizontalHeaderLabels(["№", "Награда"])
        self.signing_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.signing_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.signing_table.setSelectionBehavior(QAbstractItemView.SelectRows)
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

        # ── authorized table ────────────────────────────────────────────
        auth_group = QGroupBox("Уполномоченный по наградам")
        ag_layout = QVBoxLayout(auth_group)

        self.auth_table = QTableWidget()
        self.auth_table.setColumnCount(2)
        self.auth_table.setHorizontalHeaderLabels(["№", "Награда"])
        self.auth_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.auth_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.auth_table.setSelectionBehavior(QAbstractItemView.SelectRows)
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
        self.phone_edit.setText(data.get("phone", ""))
        self.email_edit.setText(data.get("email", ""))
        self.active_check.setChecked(data.get("is_active", False))
        self.notes_edit.setPlainText(data.get("notes", ""))

        self._load_signing_rights()

    def _load_signing_rights(self):
        if self._member_id is None:
            return
        try:
            rights = self.api.get_signing_rights(self._member_id)
        except APIError:
            rights = []

        self._signing_data = [r for r in rights if r.get("right_type") == "signer"]
        self._authorized_data = [r for r in rights if r.get("right_type") == "authorized"]

        self._fill_rights_table(self.signing_table, self._signing_data)
        self._fill_rights_table(self.auth_table, self._authorized_data)

    @staticmethod
    def _fill_rights_table(table: QTableWidget, items: list):
        table.setRowCount(0)
        for i, item in enumerate(items):
            table.insertRow(i)
            table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            table.setItem(i, 1, QTableWidgetItem(item.get("award_name", f"Награда #{item.get('award_id', '?')}")))

    # ── slots ────────────────────────────────────────────────────────────

    def _on_save(self):
        if self._member_id is None:
            return
        data = {
            "full_name": self.full_name_edit.text().strip(),
            "position": self.position_edit.text().strip(),
            "organization": self.organization_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "email": self.email_edit.text().strip(),
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
            self.api.assign_signing_right(self._member_id, {"award_id": award_id, "right_type": "signer"})
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
            self.api.assign_signing_right(self._member_id, {"award_id": award_id, "right_type": "authorized"})
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
        if row < 0 or row >= len(data_list):
            return
        right_id = data_list[row].get("id")
        if right_id is None:
            return
        try:
            self.api.remove_signing_right(right_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e}")
            return
        self._load_signing_rights()
