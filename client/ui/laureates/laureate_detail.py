from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QPushButton,
    QLabel, QTextEdit, QMessageBox, QAbstractItemView, QGroupBox,
    QProgressBar,
)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QColor

from api_client import APIError

CATEGORIES = [
    ("employee", "Сотрудники"),
    ("veteran", "Ветераны"),
    ("university", "Университеты"),
    ("nii", "НИИ"),
    ("nonprofit", "Некомм. орг."),
    ("commercial", "Комм. орг."),
]

CATEGORY_DISPLAY = dict(CATEGORIES)

LIFECYCLE_STAGES = [
    "nomination_done", "voting_done", "decision_done",
    "registration_done", "ceremony_done", "publication_done",
]


class LaureateDetailPage(QWidget):
    back_requested = pyqtSignal()
    open_lifecycle = pyqtSignal(int)  # laureate_award_id

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._laureate_id: int | None = None
        self._original_data: dict = {}
        self._dirty = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_silent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        top_bar = QHBoxLayout()
        btn_back = QPushButton("← Назад")
        btn_back.clicked.connect(self._on_back)
        top_bar.addWidget(btn_back)

        self.title_label = QLabel("Карточка лауреата")
        self.title_label.setProperty("class", "page-title")
        top_bar.addWidget(self.title_label, 1)

        btn_delete = QPushButton("Удалить")
        btn_delete.setStyleSheet("color: #D32F2F;")
        btn_delete.clicked.connect(self._on_delete)
        top_bar.addWidget(btn_delete)
        layout.addLayout(top_bar)

        info_group = QGroupBox("Основные данные")
        form = QFormLayout(info_group)
        form.setSpacing(8)

        self.full_name = QLineEdit()
        self.full_name.textChanged.connect(self._mark_dirty)
        form.addRow("ФИО:", self.full_name)

        self.category = QComboBox()
        self.category.addItem("— не указана —", "")
        for val, label in CATEGORIES:
            self.category.addItem(label, val)
        self.category.currentIndexChanged.connect(self._mark_dirty)
        form.addRow("Категория:", self.category)

        self.position = QLineEdit()
        self.position.textChanged.connect(self._mark_dirty)
        form.addRow("Должность:", self.position)

        self.organization = QLineEdit()
        self.organization.textChanged.connect(self._mark_dirty)
        form.addRow("Организация:", self.organization)

        self.phone = QLineEdit()
        self.phone.textChanged.connect(self._mark_dirty)
        form.addRow("Телефон:", self.phone)

        self.email = QLineEdit()
        self.email.textChanged.connect(self._mark_dirty)
        form.addRow("Email:", self.email)

        self.address = QLineEdit()
        self.address.textChanged.connect(self._mark_dirty)
        form.addRow("Адрес:", self.address)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(70)
        self.notes.textChanged.connect(self._mark_dirty)
        form.addRow("Примечания:", self.notes)

        btn_save = QPushButton("Сохранить")
        btn_save.setProperty("class", "accent-btn")
        btn_save.clicked.connect(self._on_save)
        form.addRow("", btn_save)

        layout.addWidget(info_group)

        awards_label = QLabel("Привязанные награды")
        awards_label.setProperty("class", "section-title")
        layout.addWidget(awards_label)

        self.awards_table = QTableWidget()
        self.awards_table.setColumnCount(5)
        self.awards_table.setHorizontalHeaderLabels([
            "ID связки", "Награда (ID)", "Дата назначения", "Статус", "Прогресс ЖЦ",
        ])
        header = self.awards_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

        self.awards_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.awards_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.awards_table.verticalHeader().setVisible(False)
        self.awards_table.doubleClicked.connect(self._on_award_double_click)
        layout.addWidget(self.awards_table)

    def load_laureate(self, laureate_id: int):
        self._laureate_id = laureate_id
        try:
            data = self.api.get_laureate(laureate_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить лауреата:\n{e.detail}")
            return
        self._populate_fields(data)
        self._load_awards()
        self._dirty = False

    def _populate_fields(self, data: dict):
        self._original_data = dict(data)
        self.title_label.setText(f"Карточка: {data.get('full_name', '')}")
        self.full_name.setText(data.get("full_name", ""))

        cat = data.get("category", "")
        idx = self.category.findData(cat or "")
        self.category.setCurrentIndex(max(idx, 0))

        self.position.setText(data.get("position", "") or "")
        self.organization.setText(data.get("organization", "") or "")
        self.phone.setText(data.get("phone", "") or "")
        self.email.setText(data.get("email", "") or "")
        self.address.setText(data.get("address", "") or "")
        self.notes.setPlainText(data.get("notes", "") or "")

    def _load_awards(self):
        if self._laureate_id is None:
            return
        try:
            awards = self.api.get_laureate_awards(self._laureate_id)
        except APIError:
            awards = []

        self.awards_table.setRowCount(len(awards))
        for row, la in enumerate(awards):
            la_id = la.get("id", "")
            self.awards_table.setItem(row, 0, self._make_item(str(la_id)))
            self.awards_table.setItem(row, 1, self._make_item(str(la.get("award_id", ""))))
            self.awards_table.setItem(row, 2, self._make_item(str(la.get("assigned_date", "") or "")))
            self.awards_table.setItem(row, 3, self._make_item(la.get("status", "")))

            progress = self._get_lifecycle_progress(la_id)
            pbar = QProgressBar()
            pbar.setRange(0, 6)
            pbar.setValue(progress)
            pbar.setFormat(f"{progress}/6 этапов")
            pbar.setTextVisible(True)
            if progress == 6:
                pbar.setStyleSheet("QProgressBar::chunk { background: #4CAF50; }")
            elif progress > 0:
                pbar.setStyleSheet("QProgressBar::chunk { background: #FFC107; }")
            else:
                pbar.setStyleSheet("QProgressBar::chunk { background: #E0E0E0; }")
            self.awards_table.setCellWidget(row, 4, pbar)

    def _get_lifecycle_progress(self, laureate_award_id: int) -> int:
        try:
            lc = self.api.get_laureate_lifecycle(laureate_award_id)
        except APIError:
            return 0
        return sum(1 for stage in LIFECYCLE_STAGES if lc.get(stage))

    @staticmethod
    def _make_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _mark_dirty(self):
        self._dirty = True
        self._autosave_timer.start(1500)

    def _autosave_silent(self):
        self._on_save(silent=True)

    def _collect_data(self) -> dict:
        data: dict = {"full_name": self.full_name.text().strip()}
        cat = self.category.currentData()
        if cat:
            data["category"] = cat
        else:
            data["category"] = None
        for field in ("position", "organization", "phone", "email", "address"):
            data[field] = getattr(self, field).text().strip() or None
        data["notes"] = self.notes.toPlainText().strip() or None
        return data

    def _on_save(self, silent: bool = False):
        if self._laureate_id is None:
            return
        data = self._collect_data()
        if not data.get("full_name"):
            if not silent:
                QMessageBox.warning(self, "Ошибка", "Поле «ФИО» обязательно.")
            return
        try:
            updated = self.api.update_laureate(self._laureate_id, data)
            self._populate_fields(updated)
            self._dirty = False
            if not silent:
                QMessageBox.information(self, "Сохранено", "Данные лауреата обновлены.")
        except APIError as e:
            if not silent:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить:\n{e.detail}")

    def _on_delete(self):
        if self._laureate_id is None:
            return
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить лауреата «{self.full_name.text()}»?\nЭто действие необратимо.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.api.delete_laureate(self._laureate_id)
                QMessageBox.information(self, "Удалено", "Лауреат удалён.")
                self.back_requested.emit()
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e.detail}")

    def _on_back(self):
        if not self.confirm_quit_application():
            return
        self.back_requested.emit()

    def confirm_quit_application(self) -> bool:
        if not self._dirty:
            return True
        # автосохранение перед выходом/переходом
        self._on_save(silent=True)
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "Сохранить изменения?",
            "Имеются несохранённые изменения. Сохранить перед выходом?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            self._on_save()
        return True

    def _on_award_double_click(self, index):
        row = index.row()
        la_id_item = self.awards_table.item(row, 0)
        if la_id_item:
            self.open_lifecycle.emit(int(la_id_item.text()))
