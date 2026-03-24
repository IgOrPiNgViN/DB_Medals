from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QFormLayout,
    QLineEdit, QTextEdit, QDateEdit, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QMessageBox, QAbstractItemView, QDialog, QGroupBox, QScrollArea,
    QSizePolicy,
)
from PyQt5.QtCore import pyqtSignal, Qt, QDate

from api_client import APIClient, APIError

APPROVAL_TYPES = ["НК", "Геральдисты", "Родственники", "Спонсоры"]

PRODUCTION_COMPONENT_TYPES = [
    "Медаль",
    "Значок",
    "Кулон",
    "Запонки",
    "Удостоверение",
    "Футляр",
    "Колодка",
    "Другое",
]


# ── Helper: simple add-row dialog ────────────────────────────────────────

class _AddRowDialog(QDialog):
    """Generic dialog that shows a form and returns a dict of values."""

    def __init__(self, title: str, fields: list[tuple[str, str, type]], parent=None):
        """
        *fields*: list of (label, key, widget_type).
        widget_type is one of: str, 'combo', 'date', 'text'.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setModal(True)
        self._widgets: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        for label, key, wtype in fields:
            if wtype == "combo":
                w = QComboBox()
                self._widgets[key] = w
            elif wtype == "date":
                w = QDateEdit()
                w.setCalendarPopup(True)
                w.setDate(QDate.currentDate())
                self._widgets[key] = w
            elif wtype == "text":
                w = QTextEdit()
                w.setMaximumHeight(80)
                self._widgets[key] = w
            else:
                w = QLineEdit()
                self._widgets[key] = w
            form.addRow(label, w)

        layout.addLayout(form)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Отмена")
        cancel.setProperty("class", "btn-secondary")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        ok = QPushButton("Добавить")
        ok.setProperty("class", "btn-success")
        ok.clicked.connect(self.accept)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def combo_widget(self, key: str) -> QComboBox:
        return self._widgets[key]

    def get_data(self) -> dict:
        result = {}
        for key, w in self._widgets.items():
            if isinstance(w, QComboBox):
                result[key] = w.currentText()
            elif isinstance(w, QDateEdit):
                result[key] = w.date().toString("yyyy-MM-dd")
            elif isinstance(w, QTextEdit):
                result[key] = w.toPlainText().strip()
            else:
                result[key] = w.text().strip()
        return result


# ── Tab: Характеристика ─────────────────────────────────────────────────

class _CharacteristicsTab(QWidget):
    dirty_changed = pyqtSignal(bool)

    def __init__(self, api: APIClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.award_id: int | None = None
        self._dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.NoFrame)
        container = QWidget()
        self.form = QFormLayout(container)
        self.form.setSpacing(10)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self.fields: dict[str, QLineEdit] = {}
        for label, key in [
            ("Название:", "name"),
            ("Тип:", "award_type"),
            ("Описание:", "description"),
            ("Статус:", "status"),
        ]:
            edit = QLineEdit()
            edit.textChanged.connect(self._mark_dirty)
            self.fields[key] = edit
            self.form.addRow(label, edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

    def load(self, award_id: int):
        self.award_id = award_id
        try:
            data = self.api.get_award(award_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить награду.\n{e}")
            return
        for key, edit in self.fields.items():
            edit.blockSignals(True)
            edit.setText(str(data.get(key, "") or ""))
            edit.blockSignals(False)
        self._set_dirty(False)

    def _mark_dirty(self):
        self._set_dirty(True)

    def _set_dirty(self, v: bool):
        self._dirty = v
        self.dirty_changed.emit(v)

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _save(self):
        if self.award_id is None:
            return
        payload = {k: ed.text().strip() for k, ed in self.fields.items()}
        try:
            self.api.update_award(self.award_id, payload)
            self._set_dirty(False)
            QMessageBox.information(self, "Сохранено", "Характеристики награды сохранены.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить.\n{e}")


# ── Tab: Учреждение ─────────────────────────────────────────────────────

class _EstablishmentTab(QWidget):
    dirty_changed = pyqtSignal(bool)

    FIELDS = [
        ("Дата учреждения:", "establishment_date", "date"),
        ("Номер документа:", "document_number", "str"),
        ("Дата документа:", "document_date", "date"),
        ("Инициатор:", "initiator", "str"),
        ("Детали:", "details", "text"),
    ]

    def __init__(self, api: APIClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.award_id: int | None = None
        self._dirty = False
        self._exists = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        self.form = QFormLayout()
        self.form.setSpacing(10)

        self.widgets: dict[str, QWidget] = {}
        for label, key, wtype in self.FIELDS:
            if wtype == "date":
                w = QDateEdit()
                w.setCalendarPopup(True)
                w.setDate(QDate.currentDate())
                w.dateChanged.connect(self._mark_dirty)
            elif wtype == "text":
                w = QTextEdit()
                w.setMaximumHeight(100)
                w.textChanged.connect(self._mark_dirty)
            else:
                w = QLineEdit()
                w.textChanged.connect(self._mark_dirty)
            self.widgets[key] = w
            self.form.addRow(label, w)

        root.addLayout(self.form)
        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

    def load(self, award_id: int):
        self.award_id = award_id
        try:
            data = self.api.get_establishment(award_id)
            self._exists = True
        except APIError:
            data = {}
            self._exists = False

        for key, w in self.widgets.items():
            w.blockSignals(True)
            val = data.get(key, "")
            if isinstance(w, QDateEdit):
                if val:
                    w.setDate(QDate.fromString(str(val)[:10], "yyyy-MM-dd"))
                else:
                    w.setDate(QDate.currentDate())
            elif isinstance(w, QTextEdit):
                w.setPlainText(str(val or ""))
            else:
                w.setText(str(val or ""))
            w.blockSignals(False)
        self._set_dirty(False)

    def _mark_dirty(self):
        self._set_dirty(True)

    def _set_dirty(self, v: bool):
        self._dirty = v
        self.dirty_changed.emit(v)

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _collect(self) -> dict:
        result = {}
        for key, w in self.widgets.items():
            if isinstance(w, QDateEdit):
                result[key] = w.date().toString("yyyy-MM-dd")
            elif isinstance(w, QTextEdit):
                result[key] = w.toPlainText().strip()
            else:
                result[key] = w.text().strip()
        return result

    def _save(self):
        if self.award_id is None:
            return
        payload = self._collect()
        try:
            if self._exists:
                self.api.update_establishment(self.award_id, payload)
            else:
                self.api.create_establishment(self.award_id, payload)
                self._exists = True
            self._set_dirty(False)
            QMessageBox.information(self, "Сохранено", "Данные учреждения сохранены.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить.\n{e}")


# ── Tab: Разработка ─────────────────────────────────────────────────────

class _DevelopmentTab(QWidget):
    dirty_changed = pyqtSignal(bool)

    FIELDS = [
        ("Разработчик:", "developer", "str"),
        ("Дата начала:", "start_date", "date"),
        ("Дата окончания:", "end_date", "date"),
        ("Статус:", "status", "str"),
        ("Детали:", "details", "text"),
    ]

    def __init__(self, api: APIClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.award_id: int | None = None
        self._dirty = False
        self._exists = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        self.form = QFormLayout()
        self.form.setSpacing(10)

        self.widgets: dict[str, QWidget] = {}
        for label, key, wtype in self.FIELDS:
            if wtype == "date":
                w = QDateEdit()
                w.setCalendarPopup(True)
                w.setDate(QDate.currentDate())
                w.dateChanged.connect(self._mark_dirty)
            elif wtype == "text":
                w = QTextEdit()
                w.setMaximumHeight(100)
                w.textChanged.connect(self._mark_dirty)
            else:
                w = QLineEdit()
                w.textChanged.connect(self._mark_dirty)
            self.widgets[key] = w
            self.form.addRow(label, w)

        root.addLayout(self.form)
        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

    def load(self, award_id: int):
        self.award_id = award_id
        try:
            data = self.api.get_development(award_id)
            self._exists = True
        except APIError:
            data = {}
            self._exists = False

        for key, w in self.widgets.items():
            w.blockSignals(True)
            val = data.get(key, "")
            if isinstance(w, QDateEdit):
                if val:
                    w.setDate(QDate.fromString(str(val)[:10], "yyyy-MM-dd"))
                else:
                    w.setDate(QDate.currentDate())
            elif isinstance(w, QTextEdit):
                w.setPlainText(str(val or ""))
            else:
                w.setText(str(val or ""))
            w.blockSignals(False)
        self._set_dirty(False)

    def _mark_dirty(self):
        self._set_dirty(True)

    def _set_dirty(self, v: bool):
        self._dirty = v
        self.dirty_changed.emit(v)

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _collect(self) -> dict:
        result = {}
        for key, w in self.widgets.items():
            if isinstance(w, QDateEdit):
                result[key] = w.date().toString("yyyy-MM-dd")
            elif isinstance(w, QTextEdit):
                result[key] = w.toPlainText().strip()
            else:
                result[key] = w.text().strip()
        return result

    def _save(self):
        if self.award_id is None:
            return
        payload = self._collect()
        try:
            if self._exists:
                self.api.update_development(self.award_id, payload)
            else:
                self.api.create_development(self.award_id, payload)
                self._exists = True
            self._set_dirty(False)
            QMessageBox.information(self, "Сохранено", "Данные разработки сохранены.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить.\n{e}")


# ── Tab: Согласование ───────────────────────────────────────────────────

class _ApprovalsTab(QWidget):
    COLUMNS = ["№", "Тип", "Дата", "Статус", "Комментарий"]

    def __init__(self, api: APIClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.award_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_add = QPushButton("Добавить согласование")
        self.btn_add.clicked.connect(self._on_add)
        btn_row.addWidget(self.btn_add)
        root.addLayout(btn_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

    def load(self, award_id: int):
        self.award_id = award_id
        try:
            items = self.api.get_approvals(award_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить согласования.\n{e}")
            return

        self.table.setRowCount(0)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(str(item.get("id", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("approval_type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("date", "")))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("status", "")))
            self.table.setItem(row, 4, QTableWidgetItem(item.get("comment", "")))

    def _on_add(self):
        if self.award_id is None:
            return
        dlg = _AddRowDialog("Новое согласование", [
            ("Тип:", "approval_type", "combo"),
            ("Дата:", "date", "date"),
            ("Статус:", "status", "str"),
            ("Комментарий:", "comment", "text"),
        ], self)
        combo = dlg.combo_widget("approval_type")
        for t in APPROVAL_TYPES:
            combo.addItem(t)

        if dlg.exec_() == QDialog.Accepted:
            try:
                self.api.create_approval(self.award_id, dlg.get_data())
                self.load(self.award_id)
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось добавить согласование.\n{e}")


# ── Tab: Производство ───────────────────────────────────────────────────

class _ProductionsTab(QWidget):
    COLUMNS = ["№", "Компонент", "Производитель", "Дата заказа", "Кол-во", "Статус"]

    def __init__(self, api: APIClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.award_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_add = QPushButton("Добавить заказ")
        self.btn_add.clicked.connect(self._on_add)
        btn_row.addWidget(self.btn_add)
        root.addLayout(btn_row)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

    def load(self, award_id: int):
        self.award_id = award_id
        try:
            items = self.api.get_productions(award_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить производство.\n{e}")
            return

        self.table.setRowCount(0)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(str(item.get("id", ""))))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("component_type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("manufacturer", "")))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("order_date", "")))
            self.table.setItem(row, 4, QTableWidgetItem(str(item.get("quantity", ""))))
            self.table.setItem(row, 5, QTableWidgetItem(item.get("status", "")))

    def _on_add(self):
        if self.award_id is None:
            return
        dlg = _AddRowDialog("Новый заказ на производство", [
            ("Компонент:", "component_type", "combo"),
            ("Производитель:", "manufacturer", "str"),
            ("Дата заказа:", "order_date", "date"),
            ("Количество:", "quantity", "str"),
            ("Статус:", "status", "str"),
        ], self)
        combo = dlg.combo_widget("component_type")
        for t in PRODUCTION_COMPONENT_TYPES:
            combo.addItem(t)

        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if data.get("quantity"):
                try:
                    data["quantity"] = int(data["quantity"])
                except ValueError:
                    QMessageBox.warning(self, "Ошибка", "Количество должно быть числом.")
                    return
            try:
                self.api.create_production(self.award_id, data)
                self.load(self.award_id)
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось добавить заказ.\n{e}")


# ═════════════════════════════════════════════════════════════════════════
#  Main detail page
# ═════════════════════════════════════════════════════════════════════════

class AwardDetailPage(QWidget):
    """Tabbed detail view for a single award."""

    go_back = pyqtSignal()

    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api = api_client
        self.award_id: int | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        self.btn_back = QPushButton("\u2190  Назад к списку")
        self.btn_back.setProperty("class", "btn-secondary")
        self.btn_back.setFixedWidth(180)
        self.btn_back.clicked.connect(self._on_back)
        header.addWidget(self.btn_back)

        self.title_label = QLabel("Награда")
        self.title_label.setProperty("class", "page-title")
        self.title_label.setStyleSheet("padding: 0;")
        header.addWidget(self.title_label, 1)

        root.addLayout(header)

        self.tabs = QTabWidget()

        self.tab_chars = _CharacteristicsTab(self.api)
        self.tab_chars.dirty_changed.connect(self._update_title_dirty)
        self.tabs.addTab(self.tab_chars, "Характеристика")

        self.tab_estab = _EstablishmentTab(self.api)
        self.tab_estab.dirty_changed.connect(self._update_title_dirty)
        self.tabs.addTab(self.tab_estab, "Учреждение")

        self.tab_dev = _DevelopmentTab(self.api)
        self.tab_dev.dirty_changed.connect(self._update_title_dirty)
        self.tabs.addTab(self.tab_dev, "Разработка")

        self.tab_approvals = _ApprovalsTab(self.api)
        self.tabs.addTab(self.tab_approvals, "Согласование")

        self.tab_productions = _ProductionsTab(self.api)
        self.tabs.addTab(self.tab_productions, "Производство")

        root.addWidget(self.tabs, 1)

    # ── public ───────────────────────────────────────────────────────

    def load_award(self, award_id: int):
        self.award_id = award_id
        self.title_label.setText(f"Награда ID {award_id}")
        self.tab_chars.load(award_id)
        self.tab_estab.load(award_id)
        self.tab_dev.load(award_id)
        self.tab_approvals.load(award_id)
        self.tab_productions.load(award_id)

        name = self.tab_chars.fields.get("name")
        if name and name.text():
            self.title_label.setText(f"Награда: {name.text()}")

    # ── unsaved changes guard ────────────────────────────────────────

    def _has_unsaved(self) -> bool:
        return (
            self.tab_chars.is_dirty
            or self.tab_estab.is_dirty
            or self.tab_dev.is_dirty
        )

    def _update_title_dirty(self, _dirty: bool):
        base = self.title_label.text().rstrip(" *")
        if self._has_unsaved():
            self.title_label.setText(base + " *")
        else:
            self.title_label.setText(base)

    def _confirm_discard(self) -> bool:
        if not self._has_unsaved():
            return True
        answer = QMessageBox.question(
            self,
            "Несохранённые изменения",
            "Есть несохранённые изменения. Покинуть страницу без сохранения?",
            QMessageBox.Yes | QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _on_back(self):
        if self._confirm_discard():
            self.go_back.emit()
