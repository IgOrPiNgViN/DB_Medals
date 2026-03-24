from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt

from api_client import APIClient, APIError

AWARD_TYPE_FILTER = [
    ("Все", None),
    ("Медали", "Медали"),
    ("ППЗ", "ППЗ"),
    ("Знаки отличия", "Знаки отличия"),
    ("Украшения", "Украшения"),
]


class CreateAwardDialog(QDialog):
    """Modal dialog for creating a new award."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новая награда")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите название награды")
        form.addRow("Название:", self.name_edit)

        self.type_combo = QComboBox()
        for label, value in AWARD_TYPE_FILTER[1:]:
            self.type_combo.addItem(label, value)
        form.addRow("Тип:", self.type_combo)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Краткое описание (необязательно)")
        form.addRow("Описание:", self.description_edit)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setProperty("class", "btn-secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("Создать")
        ok_btn.setProperty("class", "btn-success")
        ok_btn.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _validate_and_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите название награды.")
            return
        self.accept()

    def get_data(self) -> dict:
        data = {
            "name": self.name_edit.text().strip(),
            "award_type": self.type_combo.currentData(),
        }
        desc = self.description_edit.text().strip()
        if desc:
            data["description"] = desc
        return data


class AwardsCardsPage(QWidget):
    """Page showing all awards as a filterable table."""

    award_selected = pyqtSignal(int)

    COLUMNS = ["№", "Название", "Тип", "Дата создания"]

    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(16)

        title = QLabel("Карточки наград")
        title.setProperty("class", "page-title")
        title.setStyleSheet("padding: 0;")
        root.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        toolbar.addWidget(QLabel("Тип награды:"))
        self.filter_combo = QComboBox()
        self.filter_combo.setMinimumWidth(180)
        for label, _ in AWARD_TYPE_FILTER:
            self.filter_combo.addItem(label)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_combo)

        toolbar.addStretch()

        self.btn_add = QPushButton("Новая награда")
        self.btn_add.setProperty("class", "btn-success")
        self.btn_add.clicked.connect(self._on_create)
        toolbar.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Удалить награду")
        self.btn_delete.setProperty("class", "btn-danger")
        self.btn_delete.clicked.connect(self._on_delete)
        toolbar.addWidget(self.btn_delete)

        root.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_double_click)
        root.addWidget(self.table, 1)

    # ── data loading ─────────────────────────────────────────────────

    def refresh(self):
        _, type_value = AWARD_TYPE_FILTER[self.filter_combo.currentIndex()]
        try:
            awards = self.api.get_awards(award_type=type_value)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось загрузить награды.\n{e}")
            return

        self.table.setRowCount(0)
        self.table.setRowCount(len(awards))
        for row, award in enumerate(awards):
            self.table.setItem(row, 0, self._item(str(award.get("id", ""))))
            self.table.setItem(row, 1, self._item(award.get("name", "")))
            self.table.setItem(row, 2, self._item(award.get("award_type", "")))
            self.table.setItem(row, 3, self._item(award.get("created_at", "")))

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    @staticmethod
    def _item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    # ── slots ────────────────────────────────────────────────────────

    def _on_filter_changed(self):
        self.refresh()

    def _on_double_click(self, index):
        row = index.row()
        id_item = self.table.item(row, 0)
        if id_item:
            try:
                award_id = int(id_item.text())
                self.award_selected.emit(award_id)
            except ValueError:
                pass

    def _on_create(self):
        dlg = CreateAwardDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                self.api.create_award(dlg.get_data())
                self.refresh()
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать награду.\n{e}")

    def _on_delete(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Удаление", "Выберите награду для удаления.")
            return

        row = rows[0].row()
        name = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        award_id_text = self.table.item(row, 0).text() if self.table.item(row, 0) else ""

        answer = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f'Удалить награду "{name}" (ID {award_id_text})?',
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self.api.delete_award(int(award_id_text))
            self.refresh()
        except (APIError, ValueError) as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить награду.\n{e}")
