from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QLabel, QGroupBox,
    QFormLayout, QLineEdit, QMessageBox, QAbstractItemView, QDialog,
    QSpinBox, QFileDialog, QComboBox, QDialogButtonBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush

from api_client import APIClient, APIError
from ui.tab_helpers import configure_tab_bar_no_clip
from ui.print_helpers import print_table, pdf_table
from ui.numeric_sort_item import NumericSortTableItem
from ui.fetch_worker import run_api_fetch, thread_api_call
from ui.awards_cache import AwardsCache
from ui.table_fill import configure_table_rows

AWARD_TABS = [
    ("Медали", "Медали"),
    ("ППЗ", "ППЗ"),
    ("Знаки отличия", "Знаки отличия"),
    ("Украшения", "Украшения"),
]

TAB_API_TYPE = {
    "Медали": "medal",
    "ППЗ": "ppz",
    "Знаки отличия": "distinction",
    "Украшения": "decoration",
}

API_TYPE_RU = {v: k for k, v in TAB_API_TYPE.items()}

SUMMARY_HEADERS = {
    "Медали": [
        "Награда", "Комплекты", "Медали", "Зн.(з)", "Зн.(с)", "Зн.(з-с)", "Зн.(л)", "Удост.", "Коробки",
    ],
    "ППЗ": ["Награда", "Комплекты", "ППЗ", "Удост.", "Значки", "Коробки"],
    "Знаки отличия": ["Награда", "Значки", "Удост."],
    "Украшения": ["Награда", "Запонки", "Кор.(з)", "Кулоны", "Цепочки", "Кор.(к)"],
}

INVENTORY_COLUMNS = [
    "№",
    "Награда",
    "Компонент",
    "Всего",
    "Резерв",
    "Выдано",
    "Доступно",
]

LOW_STOCK_THRESHOLD = 10
LOW_STOCK_BG = QColor(255, 205, 210)

KIT_TYPE_OPTIONS = [
    ("", "Полный комплект"),
    ("медаль", "Медаль"),
    ("ппз", "ППЗ"),
    ("значок латунь", "Значок (латунь)"),
    ("значок серебро", "Значок (серебро)"),
    ("значок золото", "Значок (золото)"),
    ("значок з-с", "Значок (з-с)"),
]


class _KitLaureateDisposalDialog(QDialog):
    """Выбытие комплекта лауреату (ТЗ file-012, кнопка как в Access)."""

    def __init__(self, api: APIClient, awards: list[dict], parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Выбытие комплекта — лауреату")
        self.setMinimumWidth(460)
        layout = QFormLayout(self)

        self.award_combo = QComboBox()
        for a in awards:
            self.award_combo.addItem(a.get("name", ""), a.get("id"))
        layout.addRow("Награда:", self.award_combo)

        self.laureate_award_edit = QLineEdit()
        self.laureate_award_edit.setPlaceholderText("ID связки лауреат–награда")
        layout.addRow("ID связки:", self.laureate_award_edit)

        self.event_edit = QLineEdit()
        layout.addRow("Мероприятие:", self.event_edit)

        self.protocol_edit = QLineEdit()
        layout.addRow("Протокол:", self.protocol_edit)

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("ГГГГ-ММ-ДД")
        layout.addRow("Дата:", self.date_edit)

        self.note_edit = QLineEdit()
        layout.addRow("Примечание:", self.note_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> tuple[int, dict]:
        la_text = self.laureate_award_edit.text().strip()
        if not la_text.isdigit():
            raise ValueError("Укажите числовой ID связки лауреат–награда")
        date_text = self.date_edit.text().strip()
        return int(self.award_combo.currentData()), {
            "target": "laureate",
            "laureate_award_id": int(la_text),
            "event_name": self.event_edit.text().strip() or None,
            "protocol_number": self.protocol_edit.text().strip() or None,
            "disposal_date": date_text or None,
            "note": self.note_edit.text().strip() or None,
            "quantity": 1,
        }


class _EditInventoryDialog(QDialog):
    """Dialog for editing inventory quantities."""

    def __init__(self, item_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование остатков")
        self.setMinimumWidth(380)
        self.setModal(True)
        self._item_data = item_data

        layout = QVBoxLayout(self)
        form = QFormLayout()

        name_label = QLabel(item_data.get("award_name", ""))
        name_label.setStyleSheet("font-weight: bold;")
        form.addRow("Награда:", name_label)

        comp_label = QLabel(item_data.get("component_type", ""))
        form.addRow("Компонент:", comp_label)

        self.total_spin = QSpinBox()
        self.total_spin.setRange(0, 999999)
        self.total_spin.setValue(int(item_data.get("total_count") or item_data.get("total") or 0))
        form.addRow("Всего:", self.total_spin)

        self.reserve_spin = QSpinBox()
        self.reserve_spin.setRange(0, 999999)
        self.reserve_spin.setValue(int(item_data.get("reserve_count") or item_data.get("reserve") or 0))
        form.addRow("Резерв:", self.reserve_spin)

        self.issued_spin = QSpinBox()
        self.issued_spin.setRange(0, 999999)
        self.issued_spin.setValue(int(item_data.get("issued_count") or item_data.get("issued") or 0))
        form.addRow("Выдано:", self.issued_spin)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Отмена")
        cancel.setProperty("class", "btn-secondary")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("Сохранить")
        save.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def _on_save_clicked(self):
        t = self.total_spin.value()
        r = self.reserve_spin.value()
        i = self.issued_spin.value()
        if r + i > t:
            QMessageBox.warning(
                self,
                "Проверка",
                "Сумма резерва и выданного не может превышать общее количество.",
            )
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "total_count": self.total_spin.value(),
            "reserve_count": self.reserve_spin.value(),
            "issued_count": self.issued_spin.value(),
        }


class _KitManageDialog(QDialog):
    def __init__(self, api: APIClient, award_id: int, award_name: str, parent=None):
        super().__init__(parent)
        self.api = api
        self.award_id = award_id
        self.setWindowTitle(f"Комплекты — {award_name}")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        self.info = QLabel("Загрузка…")
        layout.addWidget(self.info)
        form = QFormLayout()
        self.kit_type_combo = QComboBox()
        for val, label in KIT_TYPE_OPTIONS:
            self.kit_type_combo.addItem(label, val or None)
        form.addRow("Тип комплекта:", self.kit_type_combo)
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.qty_spin.setValue(1)
        form.addRow("Количество:", self.qty_spin)
        layout.addLayout(form)
        btn_row = QHBoxLayout()
        btn_asm = QPushButton("Собрать комплекты")
        btn_asm.clicked.connect(self._on_assemble)
        btn_row.addWidget(btn_asm)
        btn_dis = QPushButton("Разобрать комплекты")
        btn_dis.clicked.connect(self._on_disassemble)
        btn_row.addWidget(btn_dis)
        layout.addLayout(btn_row)

        uni_group = QGroupBox("Универсальный склад → в комплект")
        ug = QFormLayout(uni_group)
        self.uni_cert_spin = QSpinBox()
        self.uni_cert_spin.setRange(0, 999999)
        self.uni_box_spin = QSpinBox()
        self.uni_box_spin.setRange(0, 999999)
        ug.addRow("Удостоверения:", self.uni_cert_spin)
        ug.addRow("Коробки:", self.uni_box_spin)
        btn_uni_save = QPushButton("Сохранить остатки универсального склада")
        btn_uni_save.clicked.connect(self._on_save_universal)
        ug.addRow(btn_uni_save)
        self.uni_label = QLabel("—")
        ug.addRow("Текущие значения:", self.uni_label)
        uni_btn = QHBoxLayout()
        btn_cert = QPushButton("В комплект: удостоверение")
        btn_cert.clicked.connect(lambda: self._on_to_kit("certificate"))
        uni_btn.addWidget(btn_cert)
        btn_box = QPushButton("В комплект: коробка")
        btn_box.clicked.connect(lambda: self._on_to_kit("box"))
        uni_btn.addWidget(btn_box)
        ug.addRow(uni_btn)
        layout.addWidget(uni_group)

        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self._refresh()

    def _refresh(self):
        try:
            st = self.api.get_kit_status(self.award_id)
            uni = self.api.get_universal_stock()
        except APIError as e:
            self.info.setText(f"Ошибка: {e.detail}")
            return
        self.info.setText(
            f"Физические: {st.get('physical_sets', 0)} | "
            f"Свободные: {st.get('free_sets', 0)} | "
            f"Отложено: {st.get('postponed_sets', 0)} | "
            f"Можно собрать: {st.get('can_assemble_from_loose', 0)}"
        )
        self.uni_label.setText(
            f"удостоверения: {uni.get('certificate_count', 0)}, "
            f"коробки: {uni.get('box_count', 0)}"
        )
        self.uni_cert_spin.blockSignals(True)
        self.uni_box_spin.blockSignals(True)
        self.uni_cert_spin.setValue(int(uni.get("certificate_count") or 0))
        self.uni_box_spin.setValue(int(uni.get("box_count") or 0))
        self.uni_cert_spin.blockSignals(False)
        self.uni_box_spin.blockSignals(False)

    def _kit_type_value(self) -> str | None:
        return self.kit_type_combo.currentData()

    def _on_save_universal(self):
        try:
            self.api.update_universal_stock({
                "certificate_count": self.uni_cert_spin.value(),
                "box_count": self.uni_box_spin.value(),
            })
            self._refresh()
            QMessageBox.information(self, "Склад", "Универсальный склад обновлён.")
        except APIError as e:
            QMessageBox.warning(self, "Склад", str(e.detail))

    def _on_assemble(self):
        try:
            self.api.assemble_kits(
                self.award_id, self.qty_spin.value(), kit_type=self._kit_type_value(),
            )
            self._refresh()
        except APIError as e:
            QMessageBox.warning(self, "Сборка", str(e.detail))

    def _on_disassemble(self):
        try:
            self.api.disassemble_kits(
                self.award_id, self.qty_spin.value(), kit_type=self._kit_type_value(),
            )
            self._refresh()
        except APIError as e:
            QMessageBox.warning(self, "Разборка", str(e.detail))

    def _on_to_kit(self, component: str):
        try:
            self.api.transfer_to_kit(self.award_id, component, self.qty_spin.value())
            self._refresh()
            QMessageBox.information(self, "Склад", "Элемент переведён в комплект награды.")
        except APIError as e:
            QMessageBox.warning(self, "В комплект", str(e.detail))


class _DecorationDisposalDialog(QDialog):
    """Регистрация выбытия украшения (ТЗ file-013)."""

    TARGETS = [
        ("laureate", "Лауреату"),
        ("event", "На мероприятие"),
        ("other", "Прочее"),
    ]

    def __init__(
        self,
        api: APIClient,
        award_id: int,
        award_name: str,
        component_type: str,
        parent=None,
    ):
        super().__init__(parent)
        self.api = api
        self.award_id = award_id
        self.setWindowTitle(f"Выбытие — {award_name}")
        self.setMinimumWidth(420)

        layout = QFormLayout(self)
        comp_label = QLabel(component_type)
        layout.addRow("Компонент:", comp_label)
        self.component_type = component_type

        self.target_combo = QComboBox()
        for val, label in self.TARGETS:
            self.target_combo.addItem(label, val)
        layout.addRow("Назначение:", self.target_combo)

        self.laureate_award_edit = QLineEdit()
        self.laureate_award_edit.setPlaceholderText("ID связки лауреат–награда")
        layout.addRow("ID связки:", self.laureate_award_edit)

        self.event_edit = QLineEdit()
        layout.addRow("Мероприятие:", self.event_edit)

        self.reason_edit = QLineEdit()
        layout.addRow("Причина:", self.reason_edit)

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("ГГГГ-ММ-ДД")
        layout.addRow("Дата выбытия:", self.date_edit)

        self.note_edit = QLineEdit()
        layout.addRow("Примечание:", self.note_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> dict:
        la_text = self.laureate_award_edit.text().strip()
        la_id = int(la_text) if la_text.isdigit() else None
        date_text = self.date_edit.text().strip()
        return {
            "component_type": self.component_type,
            "target": self.target_combo.currentData(),
            "laureate_award_id": la_id,
            "event_name": self.event_edit.text().strip() or None,
            "reason": self.reason_edit.text().strip() or None,
            "disposal_date": date_text or None,
            "note": self.note_edit.text().strip() or None,
        }


class _KitOtherDisposalDialog(QDialog):
    """Регистрация выбытия комплекта «иное» (ТЗ file-012)."""

    def __init__(self, api: APIClient, awards: list[dict], parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Выбытие комплекта — иное")
        self.setMinimumWidth(440)
        layout = QFormLayout(self)

        self.award_combo = QComboBox()
        for a in awards:
            self.award_combo.addItem(a.get("name", ""), a.get("id"))
        layout.addRow("Награда:", self.award_combo)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.qty_spin.setValue(1)
        layout.addRow("Количество:", self.qty_spin)

        self.reason_edit = QLineEdit()
        layout.addRow("Причина:", self.reason_edit)

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("ГГГГ-ММ-ДД")
        layout.addRow("Дата:", self.date_edit)

        self.note_edit = QLineEdit()
        layout.addRow("Примечание:", self.note_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> tuple[int, dict]:
        award_id = self.award_combo.currentData()
        date_text = self.date_edit.text().strip()
        return int(award_id), {
            "target": "other",
            "quantity": self.qty_spin.value(),
            "reason": self.reason_edit.text().strip() or None,
            "disposal_date": date_text or None,
            "note": self.note_edit.text().strip() or None,
        }


class WarehousePage(QWidget):
    """Warehouse / inventory page."""

    award_selected = pyqtSignal(int)
    open_lifecycle = pyqtSignal(int)

    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._data: list[dict] = []
        self._grouped: dict[str, list] = {}
        self._reservations: dict = {}
        self._kit_journal: dict = {}
        self._deco_award_id: int | None = None
        self._refresh_gen = 0
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(16)

        title = QLabel("Склад")
        title.setProperty("class", "page-title")
        title.setStyleSheet("padding: 0;")
        root.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.addStretch()

        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(self.btn_refresh)

        self.btn_edit = QPushButton("Редактировать остаток")
        self.btn_edit.clicked.connect(self._on_edit_selected)
        toolbar.addWidget(self.btn_edit)

        self.btn_kits = QPushButton("Комплекты…")
        self.btn_kits.clicked.connect(self._on_manage_kits)
        toolbar.addWidget(self.btn_kits)

        self.btn_print = QPushButton("Печать")
        self.btn_print.setProperty("class", "btn-secondary")
        self.btn_print.clicked.connect(self._on_print)
        toolbar.addWidget(self.btn_print)

        self.btn_pdf = QPushButton("В PDF…")
        self.btn_pdf.setProperty("class", "btn-secondary")
        self.btn_pdf.clicked.connect(self._on_pdf)
        toolbar.addWidget(self.btn_pdf)

        self.btn_excel = QPushButton("Выгрузка в Excel…")
        self.btn_excel.clicked.connect(self._on_excel)
        toolbar.addWidget(self.btn_excel)

        root.addLayout(toolbar)

        self.outer_tabs = QTabWidget()
        inventory_page = QWidget()
        inv_layout = QVBoxLayout(inventory_page)
        inv_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        self.tables: dict[str, QTableWidget] = {}
        self.summary_tables: dict[str, QTableWidget] = {}

        for tab_label, type_key in AWARD_TABS:
            if type_key == "Украшения":
                page = self._build_decorations_tab()
                self.tab_widget.addTab(page, tab_label)
            else:
                page = QWidget()
                pl = QVBoxLayout(page)
                pl.setContentsMargins(0, 8, 0, 0)
                pl.addWidget(QLabel("Сводка остатков (ТЗ)"))
                summary = self._make_summary_table(type_key)
                self.summary_tables[type_key] = summary
                pl.addWidget(summary)
                pl.addWidget(QLabel("Детальный учёт по компонентам"))
                table = self._make_table()
                self.tables[type_key] = table
                pl.addWidget(table, 1)
                self.tab_widget.addTab(page, tab_label)

        configure_tab_bar_no_clip(self.tab_widget)
        inv_layout.addWidget(self.tab_widget, 1)
        self.outer_tabs.addTab(inventory_page, "Учёт остатков")

        reserve_page = self._build_reservations_tab()
        self.outer_tabs.addTab(reserve_page, "Резерв и выбытие")
        configure_tab_bar_no_clip(self.outer_tabs)
        root.addWidget(self.outer_tabs, 1)

    def _make_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(INVENTORY_COLUMNS))
        table.setHorizontalHeaderLabels(INVENTORY_COLUMNS)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.doubleClicked.connect(self._on_double_click)
        table.setSortingEnabled(True)
        table.horizontalHeader().setSortIndicatorShown(True)
        configure_table_rows(table, 36)
        return table

    def _make_summary_table(self, type_key: str) -> QTableWidget:
        headers = SUMMARY_HEADERS.get(type_key, ["Награда"])
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.verticalHeader().setVisible(False)
        table.setMaximumHeight(220)
        table.horizontalHeader().setStretchLastSection(True)
        table.doubleClicked.connect(self._on_summary_double_click)
        return table

    def _summary_row_values(self, type_key: str, item: dict) -> list:
        if type_key == "ППЗ":
            return [
                item.get("award_name", ""),
                item.get("sets", 0),
                item.get("ppz", 0),
                item.get("certificates", 0),
                item.get("badges", 0),
                item.get("boxes", 0),
            ]
        if type_key == "Знаки отличия":
            return [
                item.get("award_name", ""),
                item.get("badge_brass", 0) or item.get("badges", 0),
                item.get("certificates", 0),
            ]
        if type_key == "Украшения":
            return [
                item.get("award_name", ""),
                item.get("cufflinks", 0),
                item.get("cufflink_boxes", 0),
                item.get("pendants", 0),
                item.get("chains", 0),
                item.get("pendant_boxes", 0),
            ]
        return [
            item.get("award_name", ""),
            item.get("sets", 0),
            item.get("medals", 0),
            item.get("badge_gold", 0),
            item.get("badge_silver", 0),
            item.get("badge_gold_silver", 0),
            item.get("badge_brass", 0),
            item.get("certificates", 0),
            item.get("boxes", 0),
        ]

    def _populate_summary_tables(self):
        for type_key, table in self.summary_tables.items():
            rows = self._grouped.get(type_key, [])
            table.setRowCount(len(rows))
            for i, item in enumerate(rows):
                vals = self._summary_row_values(type_key, item)
                for col, val in enumerate(vals):
                    cell = QTableWidgetItem(str(val))
                    cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    if col == 0:
                        aid = item.get("award_id")
                        if aid is not None:
                            cell.setData(Qt.UserRole, int(aid))
                    if isinstance(val, int) and 0 < val < LOW_STOCK_THRESHOLD:
                        cell.setBackground(QBrush(LOW_STOCK_BG))
                    table.setItem(i, col, cell)
            table.setProperty("_items", rows)

    def _on_summary_double_click(self, index):
        table = self.sender()
        if not isinstance(table, QTableWidget):
            return
        it = table.item(index.row(), 0)
        if it is None:
            return
        award_id = it.data(Qt.UserRole)
        if award_id is not None:
            dlg = _KitManageDialog(self.api, int(award_id), it.text(), self)
            dlg.exec_()
            self.refresh()

    def _build_decorations_tab(self) -> QWidget:
        """Separate tab for Украшения with a form section on top."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)

        group = QGroupBox("Украшения — сводка (ТЗ)")
        form = QFormLayout(group)
        self.deco_summary_table = self._make_summary_table("Украшения")
        self.summary_tables["Украшения"] = self.deco_summary_table
        form.addRow(self.deco_summary_table)
        layout.addWidget(group)

        table = self._make_table()
        self.tables["Украшения"] = table
        table.itemSelectionChanged.connect(self._on_deco_selection_changed)
        layout.addWidget(table, 1)

        adjust_row = QHBoxLayout()
        self.btn_deco_minus = QPushButton("−1 к «Всего»")
        self.btn_deco_minus.setProperty("class", "btn-secondary")
        self.btn_deco_minus.clicked.connect(lambda: self._adjust_deco_total(-1))
        adjust_row.addWidget(self.btn_deco_minus)
        self.btn_deco_plus = QPushButton("+1 к «Всего»")
        self.btn_deco_plus.clicked.connect(lambda: self._adjust_deco_total(1))
        adjust_row.addWidget(self.btn_deco_plus)
        adjust_row.addStretch()
        layout.addLayout(adjust_row)

        journal_group = QGroupBox("Журнал выбытия")
        jg = QVBoxLayout(journal_group)
        j_btn = QHBoxLayout()
        self.btn_add_disposal = QPushButton("Зарегистрировать выбытие…")
        self.btn_add_disposal.clicked.connect(self._on_register_disposal)
        j_btn.addWidget(self.btn_add_disposal)
        self.btn_refresh_disposals = QPushButton("Обновить журнал")
        self.btn_refresh_disposals.clicked.connect(self._load_disposal_journal)
        j_btn.addWidget(self.btn_refresh_disposals)
        j_btn.addStretch()
        jg.addLayout(j_btn)

        la_deco_group = QGroupBox("Лауреатам")
        la_deco_l = QVBoxLayout(la_deco_group)
        self.deco_laureate_table = self._make_deco_journal_table()
        la_deco_l.addWidget(self.deco_laureate_table)
        jg.addWidget(la_deco_group)

        other_deco_group = QGroupBox("Иное")
        other_deco_l = QVBoxLayout(other_deco_group)
        self.deco_other_table = self._make_deco_journal_table()
        other_deco_l.addWidget(self.deco_other_table)
        jg.addWidget(other_deco_group)
        layout.addWidget(journal_group, 1)

        return page

    def _make_deco_journal_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "№", "Компонент", "Назначение", "Дата", "Причина", "Примечание",
        ])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        configure_table_rows(table, 36)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _build_reservations_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)

        hint = QLabel(
            "«Резерв» — зарезервировано на складе, вручение не выполнено. "
            "«Оформлено, не вручено» — отложено (флаг в ЖЦ). "
            "«Выдано» — списано лауреатам. Двойной щелчок — жизненный цикл.",
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        reserved_group = QGroupBox("Резерв (ожидает вручения)")
        rg = QVBoxLayout(reserved_group)
        reserved_btn = QHBoxLayout()
        self.btn_remove_reserve = QPushButton("Убрать из резерва")
        self.btn_remove_reserve.clicked.connect(self._on_remove_reserve)
        reserved_btn.addWidget(self.btn_remove_reserve)
        self.btn_to_postponed = QPushButton("В отложено…")
        self.btn_to_postponed.clicked.connect(self._on_mark_postponed)
        reserved_btn.addWidget(self.btn_to_postponed)
        reserved_btn.addStretch()
        rg.addLayout(reserved_btn)
        self.reserved_table = self._make_reservation_table()
        rg.addWidget(self.reserved_table)
        layout.addWidget(reserved_group, 1)

        postponed_group = QGroupBox("Оформлено, но не вручено (отложено)")
        pg = QVBoxLayout(postponed_group)
        postponed_btn = QHBoxLayout()
        self.btn_ceremony = QPushButton("Вручение лауреату")
        self.btn_ceremony.clicked.connect(self._on_ceremony_from_postponed)
        postponed_btn.addWidget(self.btn_ceremony)
        self.btn_from_postponed = QPushButton("Снять с отложенного")
        self.btn_from_postponed.clicked.connect(self._on_clear_postponed)
        postponed_btn.addWidget(self.btn_from_postponed)
        postponed_btn.addStretch()
        pg.addLayout(postponed_btn)
        self.postponed_table = self._make_reservation_table()
        pg.addWidget(self.postponed_table)
        layout.addWidget(postponed_group, 1)

        issued_group = QGroupBox("Выбытие — выдано лауреатам")
        ig = QVBoxLayout(issued_group)
        self.issued_table = self._make_reservation_table()
        ig.addWidget(self.issued_table)
        layout.addWidget(issued_group, 1)

        kit_la_group = QGroupBox("Журнал выбытия комплектов — лауреатам")
        klg = QVBoxLayout(kit_la_group)
        la_btn = QHBoxLayout()
        self.btn_kit_laureate = QPushButton("Выбытие (лаур.)…")
        self.btn_kit_laureate.clicked.connect(self._on_register_kit_laureate)
        la_btn.addWidget(self.btn_kit_laureate)
        la_btn.addStretch()
        klg.addLayout(la_btn)
        self.kit_laureate_table = self._make_kit_disposal_table()
        self.kit_laureate_table.doubleClicked.connect(self._on_kit_journal_double_click)
        klg.addWidget(self.kit_laureate_table)
        layout.addWidget(kit_la_group, 1)

        kit_other_group = QGroupBox("Журнал выбытия комплектов — иное")
        kog = QVBoxLayout(kit_other_group)
        other_btn = QHBoxLayout()
        self.btn_kit_other = QPushButton("Зарегистрировать «иное»…")
        self.btn_kit_other.clicked.connect(self._on_register_kit_other)
        other_btn.addWidget(self.btn_kit_other)
        other_btn.addStretch()
        kog.addLayout(other_btn)
        self.kit_other_table = self._make_kit_disposal_table(other=True)
        kog.addWidget(self.kit_other_table)
        layout.addWidget(kit_other_group, 1)
        return page

    def _make_kit_disposal_table(self, other: bool = False) -> QTableWidget:
        table = QTableWidget()
        if other:
            headers = ["№", "Награда", "Кол-во", "Причина", "Дата", "Примечание"]
        else:
            headers = ["№", "Награда", "Лауреат", "Мероприятие", "Дата", "Протокол"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        configure_table_rows(table, 36)
        return table

    def _make_reservation_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["№", "Лауреат", "Награда", "Дата назначения"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.doubleClicked.connect(self._on_reservation_double_click)
        table.setSortingEnabled(True)
        table.horizontalHeader().setSortIndicatorShown(True)
        configure_table_rows(table, 36)
        return table

    def _fill_reservation_table(self, table: QTableWidget, rows: list[dict]):
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            la_id = row.get("laureate_award_id")
            no = NumericSortTableItem(str(i + 1), i + 1)
            if la_id is not None:
                no.setData(Qt.UserRole, int(la_id))
            table.setItem(i, 0, no)
            table.setItem(i, 1, QTableWidgetItem(row.get("laureate_name", "")))
            table.setItem(i, 2, QTableWidgetItem(row.get("award_name", "")))
            table.setItem(i, 3, QTableWidgetItem(str(row.get("assigned_date") or "")))
        table.setSortingEnabled(True)

    def _reservation_la_id(self, table: QTableWidget) -> int | None:
        row = table.currentRow()
        if row < 0:
            return None
        it = table.item(row, 0)
        if it is None:
            return None
        la_id = it.data(Qt.UserRole)
        return int(la_id) if la_id is not None else None

    def _on_mark_postponed(self):
        la_id = self._reservation_la_id(self.reserved_table)
        if la_id is None:
            QMessageBox.information(self, "Отложено", "Выберите строку в таблице резерва.")
            return
        try:
            self.api.update_laureate_lifecycle(la_id, {"registration_pending_issue": True})
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))
            return
        self.refresh()

    def _on_remove_reserve(self):
        la_id = self._reservation_la_id(self.reserved_table)
        if la_id is None:
            QMessageBox.information(self, "Резерв", "Выберите строку в таблице резерва.")
            return
        try:
            self.api.update_laureate_lifecycle(la_id, {"inventory_reserved": False})
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))
            return
        self.refresh()

    def _on_clear_postponed(self):
        la_id = self._reservation_la_id(self.postponed_table)
        if la_id is None:
            QMessageBox.information(self, "Отложено", "Выберите строку в таблице отложенных.")
            return
        try:
            self.api.update_laureate_lifecycle(la_id, {"registration_pending_issue": False})
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))
            return
        self.refresh()

    def _on_ceremony_from_postponed(self):
        la_id = self._reservation_la_id(self.postponed_table)
        if la_id is None:
            QMessageBox.information(self, "Вручение", "Выберите строку в таблице отложенных.")
            return
        try:
            self.api.update_laureate_lifecycle(
                la_id,
                {
                    "registration_pending_issue": False,
                    "inventory_issued": True,
                    "inventory_reserved": False,
                    "ceremony_done": True,
                },
            )
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))
            return
        self.refresh()

    def _on_reservation_double_click(self, index):
        table = self.sender()
        if not isinstance(table, QTableWidget):
            return
        it = table.item(index.row(), 0)
        if it is None:
            return
        la_id = it.data(Qt.UserRole)
        if la_id is not None:
            self.open_lifecycle.emit(int(la_id))

    # ── data ─────────────────────────────────────────────────────────

    def apply_from_cache_only(self) -> bool:
        if AwardsCache.warehouse is None:
            return False
        self._data = list(AwardsCache.warehouse)
        self._populate_tables()
        return True

    def refresh(self):
        if AwardsCache.warehouse is not None and not self._data:
            self._data = list(AwardsCache.warehouse)
            self._populate_tables()
        self._fetch_from_network()

    def _fetch_from_network(self) -> None:
        self._refresh_gen += 1
        gen = self._refresh_gen

        def fetch():
            def load(api):
                grouped = {}
                for _, type_key in AWARD_TABS:
                    api_type = TAB_API_TYPE.get(type_key)
                    if api_type:
                        grouped[type_key] = api.report_warehouse_summary_grouped(api_type)
                return (
                    api.get_warehouse_report(),
                    api.report_warehouse_reservations(),
                    grouped,
                    api.report_kit_disposals_journal(),
                )
            return thread_api_call(load)

        run_api_fetch(
            fetch,
            on_success=lambda data: self._on_data_loaded(data, gen),
            on_error=lambda err: self._on_refresh_error(err, gen),
        )

    def _on_data_loaded(self, data, gen: int):
        if gen != self._refresh_gen:
            return
        if isinstance(data, tuple) and len(data) == 4:
            warehouse_data, reservations, grouped, kit_journal = data
        elif isinstance(data, tuple) and len(data) == 3:
            warehouse_data, reservations, grouped = data
            kit_journal = {}
        elif isinstance(data, tuple) and len(data) == 2:
            warehouse_data, reservations = data
            grouped = {}
            kit_journal = {}
        else:
            warehouse_data, reservations, grouped, kit_journal = data, {}, {}, {}
        AwardsCache.set_warehouse(warehouse_data)
        self._data = warehouse_data or []
        self._grouped = grouped or {}
        self._reservations = reservations or {}
        self._kit_journal = kit_journal or {}
        self._populate_summary_tables()
        self._populate_tables()
        self._populate_reservations()
        self._populate_kit_journal()
        self._check_low_stock_alert()

    def _on_refresh_error(self, err: str, gen: int):
        if gen != self._refresh_gen:
            return
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные склада.\n{err}")

    def refresh_data(self):
        self.refresh()

    def _populate_tables(self):
        grouped: dict[str, list[dict]] = {k: [] for _, k in AWARD_TABS}
        for item in self._data:
            raw_type = item.get("award_type", "")
            t = API_TYPE_RU.get(raw_type, raw_type)
            if t in grouped:
                grouped[t].append(item)

        for type_key, table in self.tables.items():
            items = grouped.get(type_key, [])
            table.setSortingEnabled(False)
            table.setRowCount(0)
            table.setRowCount(len(items))
            for row, item in enumerate(items):
                id_val = str(item.get("id", ""))
                id_cell = NumericSortTableItem(id_val, item.get("id"))
                try:
                    id_cell.setData(Qt.UserRole, int(item.get("id")))
                except (TypeError, ValueError):
                    pass
                table.setItem(row, 0, id_cell)
                table.setItem(row, 1, QTableWidgetItem(item.get("award_name", "")))
                table.setItem(row, 2, QTableWidgetItem(item.get("component_type", "")))

                total = item.get("total_count", item.get("total", 0))
                reserve = item.get("reserve_count", item.get("reserve", 0))
                issued = item.get("issued_count", item.get("issued", 0))
                available = item.get("available_count", item.get("available", 0))

                for col, val in [(3, total), (4, reserve), (5, issued), (6, available)]:
                    cell = NumericSortTableItem(str(val), val)
                    cell.setTextAlignment(Qt.AlignCenter)
                    if col == 6 and isinstance(available, (int, float)) and available < LOW_STOCK_THRESHOLD:
                        cell.setBackground(QBrush(LOW_STOCK_BG))
                    table.setItem(row, col, cell)

            table.setProperty("_items", items)
            table.setSortingEnabled(True)

    def _on_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить Excel", "склад.xlsx", "Excel (*.xlsx);;Все файлы (*.*)",
        )
        if not path:
            return
        idx = self.tab_widget.currentIndex() if hasattr(self, "tab_widget") else -1
        type_key = AWARD_TABS[idx][1] if 0 <= idx < len(AWARD_TABS) else None
        api_type = TAB_API_TYPE.get(type_key or "")
        try:
            if api_type:
                data = self.api.download_warehouse_grouped_xlsx(api_type)
            else:
                data = self.api.download_warehouse_summary_xlsx()
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Excel", "Файл сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))

    def _selected_deco_item(self) -> dict | None:
        table = self.tables.get("Украшения")
        if table is None:
            return None
        rows = table.selectionModel().selectedRows()
        if not rows:
            return None
        items = table.property("_items") or []
        row = rows[0].row()
        id_item = table.item(row, 0)
        if id_item is None:
            return None
        inv_id = id_item.data(Qt.UserRole)
        if inv_id is None:
            try:
                inv_id = int(id_item.text())
            except ValueError:
                return None
        return next(
            (it for it in items if it.get("id") == inv_id or str(it.get("id")) == str(inv_id)),
            None,
        )

    def _adjust_deco_total(self, delta: int):
        item = self._selected_deco_item()
        if not item or item.get("id") is None:
            QMessageBox.information(self, "Склад", "Выберите строку украшения в таблице.")
            return
        total = int(item.get("total_count") or item.get("total") or 0)
        new_total = max(0, total + delta)
        if new_total == total:
            return
        try:
            self.api.update_inventory_item(
                int(item["id"]),
                {
                    "total_count": new_total,
                    "reserve_count": int(item.get("reserve_count") or item.get("reserve") or 0),
                    "issued_count": int(item.get("issued_count") or item.get("issued") or 0),
                },
            )
        except APIError as e:
            QMessageBox.critical(self, "Склад", str(e.detail))
            return
        self.refresh()

    def _on_deco_selection_changed(self):
        item = self._selected_deco_item()
        if item and item.get("award_id"):
            self._deco_award_id = int(item["award_id"])
            self._load_disposal_journal()
        else:
            self._deco_award_id = None
            self.deco_laureate_table.setRowCount(0)
            self.deco_other_table.setRowCount(0)

    def _fill_deco_journal_table(self, table: QTableWidget, rows: list[dict]):
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(str(r.get("id", ""))))
            table.setItem(i, 1, QTableWidgetItem(str(r.get("component_type") or "")))
            target = r.get("target") or ""
            if r.get("laureate_award_id"):
                target = f"лауреат (#{r['laureate_award_id']})"
            elif r.get("event_name"):
                target = f"{target}: {r['event_name']}"
            table.setItem(i, 2, QTableWidgetItem(target))
            table.setItem(i, 3, QTableWidgetItem(str(r.get("disposal_date") or "")))
            table.setItem(i, 4, QTableWidgetItem(str(r.get("reason") or "")))
            table.setItem(i, 5, QTableWidgetItem(str(r.get("note") or "")))

    def _load_disposal_journal(self):
        if not self._deco_award_id:
            return
        try:
            rows = self.api.list_decoration_disposals(self._deco_award_id)
        except APIError as e:
            QMessageBox.warning(self, "Журнал выбытия", str(e.detail))
            return
        la_rows = [r for r in rows if (r.get("target") or "").lower() == "laureate"]
        other_rows = [r for r in rows if (r.get("target") or "").lower() != "laureate"]
        self._fill_deco_journal_table(self.deco_laureate_table, la_rows)
        self._fill_deco_journal_table(self.deco_other_table, other_rows)

    def _on_register_disposal(self):
        item = self._selected_deco_item()
        if not item or not item.get("award_id"):
            QMessageBox.information(
                self, "Выбытие", "Выберите строку украшения в таблице выше.",
            )
            return
        comp = item.get("component_type") or "medal"
        dlg = _DecorationDisposalDialog(
            self.api,
            int(item["award_id"]),
            item.get("award_name", ""),
            comp,
            self,
        )
        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            self.api.create_decoration_disposal(int(item["award_id"]), dlg.get_data())
        except APIError as e:
            QMessageBox.critical(self, "Выбытие", str(e.detail))
            return
        self._deco_award_id = int(item["award_id"])
        self._load_disposal_journal()
        self.refresh()

    def _populate_reservations(self):
        if not hasattr(self, "reserved_table"):
            return
        reserved = self._reservations.get("reserved_pending") or []
        postponed = self._reservations.get("postponed_pending") or []
        issued = self._reservations.get("issued_to_laureates") or []
        self._fill_reservation_table(self.reserved_table, reserved)
        self._fill_reservation_table(self.postponed_table, postponed)
        self._fill_reservation_table(self.issued_table, issued)

    def _populate_kit_journal(self):
        if not hasattr(self, "kit_laureate_table"):
            return
        la_rows = self._kit_journal.get("laureate_disposals") or []
        other_rows = self._kit_journal.get("other_disposals") or []

        self.kit_laureate_table.setRowCount(len(la_rows))
        for i, r in enumerate(la_rows):
            no = QTableWidgetItem(str(r.get("id", "")))
            la_id = r.get("laureate_award_id")
            if la_id is not None:
                no.setData(Qt.UserRole, int(la_id))
            self.kit_laureate_table.setItem(i, 0, no)
            self.kit_laureate_table.setItem(i, 1, QTableWidgetItem(r.get("award_name", "")))
            self.kit_laureate_table.setItem(i, 2, QTableWidgetItem(r.get("laureate_name", "")))
            self.kit_laureate_table.setItem(i, 3, QTableWidgetItem(r.get("event_name") or ""))
            self.kit_laureate_table.setItem(i, 4, QTableWidgetItem(str(r.get("disposal_date") or "")))
            self.kit_laureate_table.setItem(i, 5, QTableWidgetItem(r.get("protocol_number") or ""))

        self.kit_other_table.setRowCount(len(other_rows))
        for i, r in enumerate(other_rows):
            self.kit_other_table.setItem(i, 0, QTableWidgetItem(str(r.get("id", ""))))
            self.kit_other_table.setItem(i, 1, QTableWidgetItem(r.get("award_name", "")))
            self.kit_other_table.setItem(i, 2, QTableWidgetItem(str(r.get("quantity") or 1)))
            self.kit_other_table.setItem(i, 3, QTableWidgetItem(r.get("reason") or ""))
            self.kit_other_table.setItem(i, 4, QTableWidgetItem(str(r.get("disposal_date") or "")))
            self.kit_other_table.setItem(i, 5, QTableWidgetItem(r.get("note") or ""))

    def _check_low_stock_alert(self):
        alerts: list[str] = []
        for item in self._data:
            avail = item.get("available_count", item.get("available", 0))
            if isinstance(avail, (int, float)) and 0 <= avail < LOW_STOCK_THRESHOLD:
                alerts.append(
                    f"• {item.get('award_name', '')} — {item.get('component_type', '')}: "
                    f"{int(avail)} шт."
                )
        if not alerts:
            return
        text = (
            f"На складе менее {LOW_STOCK_THRESHOLD} единиц по позициям:\n\n"
            + "\n".join(alerts[:20])
        )
        if len(alerts) > 20:
            text += f"\n… и ещё {len(alerts) - 20} позиций"
        QMessageBox.warning(self, "Низкий остаток", text)

    def _awards_for_kit_dialog(self) -> list[dict]:
        seen: set[int] = set()
        awards: list[dict] = []
        for item in self._grouped.get("Медали", []) + self._grouped.get("ППЗ", []):
            aid = item.get("award_id")
            if aid is None or aid in seen:
                continue
            seen.add(int(aid))
            awards.append({"id": int(aid), "name": item.get("award_name", "")})
        awards.sort(key=lambda x: x.get("name", ""))
        return awards

    def _on_register_kit_other(self):
        awards = self._awards_for_kit_dialog()
        if not awards:
            QMessageBox.information(self, "Выбытие", "Нет наград для регистрации.")
            return
        dlg = _KitOtherDisposalDialog(self.api, awards, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        award_id, body = dlg.get_data()
        try:
            self.api.create_kit_disposal(award_id, body)
        except APIError as e:
            QMessageBox.critical(self, "Выбытие", str(e.detail))
            return
        self.refresh()

    def _on_register_kit_laureate(self):
        awards = self._awards_for_kit_dialog()
        if not awards:
            QMessageBox.information(self, "Выбытие", "Нет наград для регистрации.")
            return
        dlg = _KitLaureateDisposalDialog(self.api, awards, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            award_id, body = dlg.get_data()
        except ValueError as e:
            QMessageBox.warning(self, "Выбытие", str(e))
            return
        try:
            self.api.create_kit_disposal(award_id, body)
        except APIError as e:
            QMessageBox.critical(self, "Выбытие", str(e.detail))
            return
        self.refresh()

    def _on_kit_journal_double_click(self, index):
        it = self.kit_laureate_table.item(index.row(), 0)
        if it is None:
            return
        la_id = it.data(Qt.UserRole)
        if la_id is not None:
            self.open_lifecycle.emit(int(la_id))

    # ── slots ────────────────────────────────────────────────────────

    def _on_double_click(self, index):
        table = self.sender()
        if not isinstance(table, QTableWidget):
            return

        row = index.row()
        items = table.property("_items")
        if not items:
            return

        id_item = table.item(row, 0)
        if not id_item:
            return
        inv_id = id_item.data(Qt.UserRole)
        if inv_id is None:
            try:
                inv_id = int(id_item.text())
            except ValueError:
                return

        item_data = next(
            (it for it in items if it.get("id") == inv_id or str(it.get("id")) == str(inv_id)),
            None,
        )
        if item_data is None:
            return
        award_id = item_data.get("award_id")
        if award_id is not None:
            dlg = _KitManageDialog(self.api, int(award_id), item_data.get("award_name", ""), self)
            if dlg.exec_() == QDialog.Accepted:
                self.refresh()
            return
        item_id = item_data.get("id")
        if item_id is None:
            return

        dlg = _EditInventoryDialog(item_data, self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                self.api.update_inventory_item(int(item_id), dlg.get_data())
                self.refresh()
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось обновить остатки.\n{e}")

    def _selected_item_data(self) -> dict | None:
        table = self._current_inventory_table()
        if table is None:
            return None
        rows = table.selectionModel().selectedRows()
        if not rows:
            return None
        items = table.property("_items") or []
        row = rows[0].row()
        id_item = table.item(row, 0)
        if not id_item:
            return None
        inv_id = id_item.data(Qt.UserRole)
        if inv_id is None:
            try:
                inv_id = int(id_item.text())
            except ValueError:
                return None
        return next(
            (it for it in items if it.get("id") == inv_id or str(it.get("id")) == str(inv_id)),
            None,
        )

    def _on_edit_selected(self):
        item_data = self._selected_item_data()
        if not item_data:
            QMessageBox.information(self, "Склад", "Выберите строку в таблице.")
            return
        item_id = item_data.get("id")
        if item_id is None:
            return
        dlg = _EditInventoryDialog(item_data, self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                self.api.update_inventory_item(int(item_id), dlg.get_data())
                self.refresh()
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось обновить остатки.\n{e}")

    def _on_manage_kits(self):
        item_data = self._selected_item_data()
        if not item_data or not item_data.get("award_id"):
            QMessageBox.information(self, "Комплекты", "Выберите строку награды.")
            return
        dlg = _KitManageDialog(
            self.api, int(item_data["award_id"]), item_data.get("award_name", ""), self,
        )
        dlg.exec_()
        self.refresh()

    def _current_inventory_table(self) -> QTableWidget | None:
        if not hasattr(self, "tab_widget"):
            return None
        idx = self.tab_widget.currentIndex()
        if idx < 0 or idx >= len(AWARD_TABS):
            return None
        type_key = AWARD_TABS[idx][1]
        return self.tables.get(type_key)

    def _on_print(self):
        if hasattr(self, "outer_tabs") and self.outer_tabs.currentIndex() == 1:
            print_table(self.reserved_table, "Склад — резерв", self)
            return
        table = self._current_inventory_table()
        if table is not None:
            tab_name = self.tab_widget.tabText(self.tab_widget.currentIndex())
            print_table(table, f"Склад — {tab_name}", self)

    def _on_pdf(self):
        table = self._current_inventory_table()
        if table is not None:
            tab_name = self.tab_widget.tabText(self.tab_widget.currentIndex())
            pdf_table(table, f"Склад — {tab_name}", self, "warehouse.pdf")
