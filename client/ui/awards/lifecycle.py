from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QLabel,
    QMessageBox, QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

from api_client import APIClient, APIError

AWARD_TABS = [
    ("Медали", "Медали"),
    ("ППЗ", "ППЗ"),
    ("Знаки отличия", "Знаки отличия"),
    ("Украшения", "Украшения"),
]

LIFECYCLE_COLUMNS = [
    "№",
    "Название",
    "Тип",
    "Учреждение",
    "Разработка",
    "Согласование",
    "Производство",
    "Статус",
]


class LifecyclePage(QWidget):
    """Report page: Жизненный цикл наград."""

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

        title = QLabel("Жизненный цикл наград")
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

        root.addLayout(toolbar)

        self.tab_widget = QTabWidget()
        self.tables: dict[str, QTableWidget] = {}

        for tab_label, type_key in AWARD_TABS:
            table = self._make_table()
            self.tables[type_key] = table
            self.tab_widget.addTab(table, tab_label)

        root.addWidget(self.tab_widget, 1)

    def _make_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(LIFECYCLE_COLUMNS))
        table.setHorizontalHeaderLabels(LIFECYCLE_COLUMNS)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.doubleClicked.connect(self._on_double_click)
        return table

    # ── data ─────────────────────────────────────────────────────────

    def refresh(self):
        try:
            self._data = self.api.get_award_lifecycle_report()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить отчёт.\n{e}")
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
                table.setItem(row, 0, QTableWidgetItem(str(item.get("id", ""))))
                table.setItem(row, 1, QTableWidgetItem(item.get("name", "")))
                table.setItem(row, 2, QTableWidgetItem(item.get("award_type", "")))
                table.setItem(row, 3, QTableWidgetItem(item.get("establishment", "")))
                table.setItem(row, 4, QTableWidgetItem(item.get("development", "")))
                table.setItem(row, 5, QTableWidgetItem(item.get("approval", "")))
                table.setItem(row, 6, QTableWidgetItem(item.get("production", "")))
                table.setItem(row, 7, QTableWidgetItem(item.get("status", "")))

    # ── slots ────────────────────────────────────────────────────────

    def _on_double_click(self, index):
        table = self.tab_widget.currentWidget()
        if not isinstance(table, QTableWidget):
            return
        id_item = table.item(index.row(), 0)
        if id_item:
            try:
                self.award_selected.emit(int(id_item.text()))
            except ValueError:
                pass

    def _on_print(self):
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QPrintDialog.Accepted:
            table = self.tab_widget.currentWidget()
            if isinstance(table, QTableWidget):
                table.render(printer)
