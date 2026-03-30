from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QLabel, QGroupBox,
    QFormLayout, QLineEdit, QMessageBox, QAbstractItemView, QDialog,
    QSpinBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush

from api_client import APIClient, APIError
from ui.tab_helpers import configure_tab_bar_no_clip
from ui.print_helpers import print_table, pdf_table

AWARD_TABS = [
    ("Медали", "Медали"),
    ("ППЗ", "ППЗ"),
    ("Знаки отличия", "Знаки отличия"),
    ("Украшения", "Украшения"),
]

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
        self.total_spin.setValue(int(item_data.get("total", 0)))
        form.addRow("Всего:", self.total_spin)

        self.reserve_spin = QSpinBox()
        self.reserve_spin.setRange(0, 999999)
        self.reserve_spin.setValue(int(item_data.get("reserve", 0)))
        form.addRow("Резерв:", self.reserve_spin)

        self.issued_spin = QSpinBox()
        self.issued_spin.setRange(0, 999999)
        self.issued_spin.setValue(int(item_data.get("issued", 0)))
        form.addRow("Выдано:", self.issued_spin)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Отмена")
        cancel.setProperty("class", "btn-secondary")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        save = QPushButton("Сохранить")
        save.clicked.connect(self.accept)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def get_data(self) -> dict:
        return {
            "total": self.total_spin.value(),
            "reserve": self.reserve_spin.value(),
            "issued": self.issued_spin.value(),
        }


class WarehousePage(QWidget):
    """Warehouse / inventory page."""

    award_selected = pyqtSignal(int)

    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._data: list[dict] = []
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

        self.btn_print = QPushButton("Печать")
        self.btn_print.setProperty("class", "btn-secondary")
        self.btn_print.clicked.connect(self._on_print)
        toolbar.addWidget(self.btn_print)

        self.btn_pdf = QPushButton("В PDF…")
        self.btn_pdf.setProperty("class", "btn-secondary")
        self.btn_pdf.clicked.connect(self._on_pdf)
        toolbar.addWidget(self.btn_pdf)

        root.addLayout(toolbar)

        self.tab_widget = QTabWidget()
        self.tables: dict[str, QTableWidget] = {}

        for tab_label, type_key in AWARD_TABS:
            if type_key == "Украшения":
                page = self._build_decorations_tab()
                self.tab_widget.addTab(page, tab_label)
            else:
                table = self._make_table()
                self.tables[type_key] = table
                self.tab_widget.addTab(table, tab_label)

        configure_tab_bar_no_clip(self.tab_widget)
        root.addWidget(self.tab_widget, 1)

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
        return table

    def _build_decorations_tab(self) -> QWidget:
        """Separate tab for Украшения with a form section on top."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)

        group = QGroupBox("Украшения — сводка")
        form = QFormLayout(group)
        self.deco_total = QLineEdit()
        self.deco_total.setReadOnly(True)
        form.addRow("Всего наименований:", self.deco_total)
        self.deco_issued = QLineEdit()
        self.deco_issued.setReadOnly(True)
        form.addRow("Выдано:", self.deco_issued)
        self.deco_available = QLineEdit()
        self.deco_available.setReadOnly(True)
        form.addRow("Доступно:", self.deco_available)
        layout.addWidget(group)

        table = self._make_table()
        self.tables["Украшения"] = table
        layout.addWidget(table, 1)
        return page

    # ── data ─────────────────────────────────────────────────────────

    def refresh(self):
        try:
            self._data = self.api.get_warehouse_report()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные склада.\n{e}")
            return
        self._populate_tables()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _populate_tables(self):
        grouped: dict[str, list[dict]] = {k: [] for _, k in AWARD_TABS}
        for item in self._data:
            t = item.get("award_type", "")
            if t in grouped:
                grouped[t].append(item)

        for type_key, table in self.tables.items():
            items = grouped.get(type_key, [])
            table.setRowCount(0)
            table.setRowCount(len(items))
            for row, item in enumerate(items):
                id_val = str(item.get("id", ""))
                table.setItem(row, 0, QTableWidgetItem(id_val))
                table.setItem(row, 1, QTableWidgetItem(item.get("award_name", "")))
                table.setItem(row, 2, QTableWidgetItem(item.get("component_type", "")))

                total = item.get("total", 0)
                reserve = item.get("reserve", 0)
                issued = item.get("issued", 0)
                available = item.get("available", 0)

                for col, val in [(3, total), (4, reserve), (5, issued), (6, available)]:
                    cell = QTableWidgetItem(str(val))
                    cell.setTextAlignment(Qt.AlignCenter)
                    if col == 6 and isinstance(available, (int, float)) and available < LOW_STOCK_THRESHOLD:
                        cell.setBackground(QBrush(LOW_STOCK_BG))
                    table.setItem(row, col, cell)

            table.setProperty("_items", items)

        deco_items = grouped.get("Украшения", [])
        total_sum = sum(it.get("total", 0) for it in deco_items if isinstance(it.get("total"), (int, float)))
        issued_sum = sum(it.get("issued", 0) for it in deco_items if isinstance(it.get("issued"), (int, float)))
        avail_sum = sum(it.get("available", 0) for it in deco_items if isinstance(it.get("available"), (int, float)))
        self.deco_total.setText(str(total_sum))
        self.deco_issued.setText(str(issued_sum))
        self.deco_available.setText(str(avail_sum))

    # ── slots ────────────────────────────────────────────────────────

    def _on_double_click(self, index):
        table = self.sender()
        if not isinstance(table, QTableWidget):
            return

        row = index.row()
        items = table.property("_items")
        if not items or row >= len(items):
            return

        item_data = items[row]
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

    def _current_inventory_table(self) -> QTableWidget | None:
        idx = self.tab_widget.currentIndex()
        if idx < 0 or idx >= len(AWARD_TABS):
            return None
        type_key = AWARD_TABS[idx][1]
        return self.tables.get(type_key)

    def _on_print(self):
        table = self._current_inventory_table()
        if table is not None:
            tab_name = self.tab_widget.tabText(self.tab_widget.currentIndex())
            print_table(table, f"Склад — {tab_name}", self)

    def _on_pdf(self):
        table = self._current_inventory_table()
        if table is not None:
            tab_name = self.tab_widget.tabText(self.tab_widget.currentIndex())
            pdf_table(table, f"Склад — {tab_name}", self, "warehouse.pdf")
