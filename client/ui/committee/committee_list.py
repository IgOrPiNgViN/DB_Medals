from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLabel, QHeaderView, QMessageBox, QAbstractItemView,
    QDialog, QFormLayout, QLineEdit, QCheckBox, QDialogButtonBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QFont

from api_client import APIError
from ui.print_helpers import print_table, pdf_table


class CreateMemberDialog(QDialog):
    """Dialog for creating a new committee member."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создать члена НК")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)

        self.full_name_edit = QLineEdit()
        self.position_edit = QLineEdit()
        self.organization_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.active_check = QCheckBox("Действующий")
        self.active_check.setChecked(True)
        self.notes_edit = QLineEdit()

        layout.addRow("ФИО:", self.full_name_edit)
        layout.addRow("Должность:", self.position_edit)
        layout.addRow("Организация:", self.organization_edit)
        layout.addRow("Телефон:", self.phone_edit)
        layout.addRow("Email:", self.email_edit)
        layout.addRow("Статус:", self.active_check)
        layout.addRow("Примечания:", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> dict:
        return {
            "full_name": self.full_name_edit.text().strip(),
            "position": self.position_edit.text().strip(),
            "organization": self.organization_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "is_active": self.active_check.isChecked(),
            "notes": self.notes_edit.text().strip(),
        }


class CommitteeListPage(QWidget):
    """Main page for the award committee member list."""

    member_selected = pyqtSignal(int)

    FILTER_MAP = {
        "Все": None,
        "Действующие": True,
        "Не действующие": False,
    }

    COLOR_ACTIVE = QColor("#E8F5E9")
    COLOR_INACTIVE = QColor("#EEEEEE")

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._member_ids: list[int] = []
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Список наградного комитета")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Фильтр:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(self.FILTER_MAP.keys())
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_combo)

        toolbar.addStretch()

        self.btn_create = QPushButton("Создать члена НК")
        self.btn_create.clicked.connect(self._on_create)
        toolbar.addWidget(self.btn_create)

        self.btn_print = QPushButton("Печать")
        self.btn_print.clicked.connect(self._on_print)
        toolbar.addWidget(self.btn_print)

        self.btn_pdf = QPushButton("В PDF…")
        self.btn_pdf.setProperty("class", "btn-secondary")
        self.btn_pdf.clicked.connect(self._on_pdf)
        toolbar.addWidget(self.btn_pdf)

        root.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["№", "ФИО", "Должность", "Организация", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._on_double_click)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.btn_assign_signer = QPushButton("Назначить подписантом удостоверения")
        self.btn_assign_signer.clicked.connect(self._on_assign_signer)
        bottom.addWidget(self.btn_assign_signer)

        self.btn_assign_authorized = QPushButton("Назначить уполномоченным")
        self.btn_assign_authorized.clicked.connect(self._on_assign_authorized)
        bottom.addWidget(self.btn_assign_authorized)

        bottom.addStretch()
        root.addLayout(bottom)

    # ── data loading ─────────────────────────────────────────────────────

    def load_data(self):
        filter_text = self.filter_combo.currentText()
        is_active = self.FILTER_MAP.get(filter_text)
        try:
            members = self.api.get_committee_members(is_active=is_active)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить список НК:\n{e}")
            return

        self._populate_table(members)

    def _populate_table(self, members: list):
        self.table.setRowCount(0)
        self._member_ids.clear()

        for row_idx, m in enumerate(members):
            self.table.insertRow(row_idx)
            self._member_ids.append(m["id"])

            is_active = m.get("is_active", False)
            bg = self.COLOR_ACTIVE if is_active else self.COLOR_INACTIVE
            status_text = "Действующий" if is_active else "Не действующий"

            items = [
                str(row_idx + 1),
                m.get("full_name", ""),
                m.get("position", ""),
                m.get("organization", ""),
                status_text,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setBackground(bg)
                if col == 0:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, col, item)

    # ── slots ────────────────────────────────────────────────────────────

    def _on_filter_changed(self):
        self.load_data()

    def _on_create(self):
        dlg = CreateMemberDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        data = dlg.get_data()
        if not data["full_name"]:
            QMessageBox.warning(self, "Ошибка", "ФИО не может быть пустым.")
            return
        try:
            self.api.create_committee_member(data)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать запись:\n{e}")
            return
        self.load_data()

    def _on_double_click(self, index):
        row = index.row()
        if 0 <= row < len(self._member_ids):
            self.member_selected.emit(self._member_ids[row])

    def _on_assign_signer(self):
        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "Информация", "Выберите члена НК.")
            return
        self.member_selected.emit(member_id)

    def _on_assign_authorized(self):
        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "Информация", "Выберите члена НК.")
            return
        self.member_selected.emit(member_id)

    def _on_print(self):
        print_table(self.table, "Список наградного комитета", self)

    def _on_pdf(self):
        pdf_table(self.table, "Список наградного комитета", self, "committee_list.pdf")

    def _selected_member_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if 0 <= row < len(self._member_ids):
            return self._member_ids[row]
        return None
