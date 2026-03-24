from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QComboBox, QPushButton, QLabel, QDialog,
    QFormLayout, QTextEdit, QMessageBox, QAbstractItemView, QDateEdit,
)
from PyQt5.QtCore import pyqtSignal, Qt, QDate

from api_client import APIError

CATEGORIES = [
    ("", "Все"),
    ("employee", "Сотрудники"),
    ("veteran", "Ветераны"),
    ("university", "Университеты"),
    ("nii", "НИИ"),
    ("nonprofit", "Некомм. орг."),
    ("commercial", "Комм. орг."),
]

CATEGORY_DISPLAY = {
    "employee": "Сотрудники",
    "veteran": "Ветераны",
    "university": "Университеты",
    "nii": "НИИ",
    "nonprofit": "Некомм. орг.",
    "commercial": "Комм. орг.",
}


class CreateLaureateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новый лауреат")
        self.setMinimumWidth(460)

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText("Иванов Иван Иванович")
        layout.addRow("ФИО *:", self.full_name)

        self.category = QComboBox()
        for val, label in CATEGORIES:
            if val:
                self.category.addItem(label, val)
        layout.addRow("Категория:", self.category)

        self.position = QLineEdit()
        layout.addRow("Должность:", self.position)

        self.organization = QLineEdit()
        layout.addRow("Организация:", self.organization)

        self.phone = QLineEdit()
        layout.addRow("Телефон:", self.phone)

        self.email = QLineEdit()
        layout.addRow("Email:", self.email)

        self.address = QLineEdit()
        layout.addRow("Адрес:", self.address)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        layout.addRow("Примечания:", self.notes)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("Создать")
        btn_save.setProperty("class", "accent-btn")
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

    def _on_save(self):
        if not self.full_name.text().strip():
            QMessageBox.warning(self, "Ошибка", "Поле «ФИО» обязательно.")
            return
        self.accept()

    def get_data(self) -> dict:
        data: dict = {"full_name": self.full_name.text().strip()}
        cat = self.category.currentData()
        if cat:
            data["category"] = cat
        for field in ("position", "organization", "phone", "email", "address"):
            val = getattr(self, field).text().strip()
            if val:
                data[field] = val
        notes = self.notes.toPlainText().strip()
        if notes:
            data["notes"] = notes
        return data


class LinkAwardDialog(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self.setWindowTitle("Связать награду с лауреатом")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.award_combo = QComboBox()
        self._load_awards()
        layout.addRow("Награда:", self.award_combo)

        self.assigned_date = QDateEdit()
        self.assigned_date.setCalendarPopup(True)
        self.assigned_date.setDate(QDate.currentDate())
        layout.addRow("Дата назначения:", self.assigned_date)

        self.bulletin_number = QLineEdit()
        layout.addRow("Номер бюллетеня:", self.bulletin_number)

        self.initiator = QLineEdit()
        layout.addRow("Инициатор:", self.initiator)

        btn_row = QHBoxLayout()
        btn_save = QPushButton("Связать")
        btn_save.setProperty("class", "accent-btn")
        btn_save.clicked.connect(self._on_save)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)
        layout.addRow(btn_row)

    def _load_awards(self):
        try:
            awards = self.api.get_awards()
            for a in awards:
                self.award_combo.addItem(a.get("name", f"#{a['id']}"), a["id"])
        except APIError as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить награды:\n{e.detail}")

    def _on_save(self):
        if self.award_combo.count() == 0:
            QMessageBox.warning(self, "Ошибка", "Нет доступных наград.")
            return
        self.accept()

    def get_data(self) -> dict:
        data: dict = {
            "award_id": self.award_combo.currentData(),
            "assigned_date": self.assigned_date.date().toString("yyyy-MM-dd"),
        }
        bn = self.bulletin_number.text().strip()
        if bn:
            data["bulletin_number"] = bn
        ini = self.initiator.text().strip()
        if ini:
            data["initiator"] = ini
        return data


class LaureateCardsPage(QWidget):
    laureate_selected = pyqtSignal(int)
    open_lifecycle = pyqtSignal(int, int)  # laureate_award_id, laureate_id

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._laureates: list = []
        self._build_ui()
        self.refresh_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Карточки лауреатов")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        toolbar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по ФИО, организации…")
        self.search_input.textChanged.connect(self._apply_filter)
        self.search_input.setMinimumWidth(250)
        toolbar.addWidget(self.search_input)

        self.category_filter = QComboBox()
        for val, label in CATEGORIES:
            self.category_filter.addItem(label, val)
        self.category_filter.currentIndexChanged.connect(self._on_category_changed)
        toolbar.addWidget(self.category_filter)

        toolbar.addStretch()

        btn_new = QPushButton("Новый лауреат")
        btn_new.setProperty("class", "accent-btn")
        btn_new.clicked.connect(self._on_create)
        toolbar.addWidget(btn_new)

        btn_link = QPushButton("Связать награду")
        btn_link.clicked.connect(self._on_link_award)
        toolbar.addWidget(btn_link)

        btn_refresh = QPushButton("Обновить")
        btn_refresh.clicked.connect(self.refresh_data)
        toolbar.addWidget(btn_refresh)

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "№", "ФИО", "Категория", "Организация", "Дата добавления",
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def refresh_data(self):
        cat = self.category_filter.currentData() if hasattr(self, "category_filter") else None
        try:
            self._laureates = self.api.get_laureates(category=cat or None)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить лауреатов:\n{e.detail}")
            self._laureates = []
        self._apply_filter()

    def _on_category_changed(self):
        self.refresh_data()

    def _apply_filter(self):
        text = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""
        filtered = self._laureates
        if text:
            filtered = [
                l for l in filtered
                if text in (l.get("full_name") or "").lower()
                or text in (l.get("organization") or "").lower()
            ]

        self.table.setRowCount(len(filtered))
        for row, l in enumerate(filtered):
            self.table.setItem(row, 0, self._make_item(str(l.get("id", ""))))
            self.table.setItem(row, 1, self._make_item(l.get("full_name", "")))
            cat = l.get("category")
            self.table.setItem(row, 2, self._make_item(CATEGORY_DISPLAY.get(cat, cat or "")))
            self.table.setItem(row, 3, self._make_item(l.get("organization", "") or ""))
            created = l.get("created_at", "")
            if created and "T" in str(created):
                created = str(created).split("T")[0]
            self.table.setItem(row, 4, self._make_item(str(created or "")))

        self.status_label.setText(f"Всего: {len(filtered)} из {len(self._laureates)}")

    @staticmethod
    def _make_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _on_double_click(self, index):
        row = index.row()
        id_item = self.table.item(row, 0)
        if id_item:
            self.laureate_selected.emit(int(id_item.text()))

    def _on_create(self):
        dlg = CreateLaureateDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                self.api.create_laureate(dlg.get_data())
                self.refresh_data()
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать лауреата:\n{e.detail}")

    def _on_link_award(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Внимание", "Выберите лауреата в таблице.")
            return
        laureate_id = int(self.table.item(row, 0).text())

        dlg = LinkAwardDialog(self.api, self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                data = dlg.get_data()
                data["laureate_id"] = laureate_id
                self.api.link_award_to_laureate(laureate_id, data)
                QMessageBox.information(self, "Успех", "Награда успешно привязана к лауреату.")
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось связать награду:\n{e.detail}")

    def _selected_laureate_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.text()) if item else None
