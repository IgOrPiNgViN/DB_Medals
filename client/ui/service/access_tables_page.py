"""Просмотр полного содержимого таблиц, как в выгрузке Access (зеркало CSV)."""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt

from api_client import APIClient, APIError


class AccessTablesPage(QWidget):
    """Список таблиц из зеркала Access и таблица со всеми колонками."""

    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(14)

        title = QLabel("Таблицы Access (как в бэкенде)")
        title.setProperty("class", "page-title")
        title.setStyleSheet("padding: 0;")
        root.addWidget(title)

        hint = QLabel(
            "Здесь те же столбцы и строки, что в CSV после dump_access_to_csv.py "
            "и импорта migration/import_from_csv.py. Выберите таблицу — отобразятся "
            "все поля, как в исходной базе."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #64748b; font-size: 12px;")
        root.addWidget(hint)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Таблица:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(420)
        bar.addWidget(self.combo, 1)
        self.btn_reload_list = QPushButton("Обновить список")
        self.btn_reload_list.setProperty("class", "btn-secondary")
        self.btn_reload_list.clicked.connect(self._load_table_list)
        bar.addWidget(self.btn_reload_list)
        self.btn_open = QPushButton("Показать")
        self.btn_open.clicked.connect(self._load_rows)
        bar.addWidget(self.btn_open)
        root.addLayout(bar)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        self._load_table_list()

    def _load_table_list(self):
        self.combo.clear()
        try:
            items = self.api.list_access_mirror_tables()
        except APIError as e:
            QMessageBox.warning(
                self,
                "Нет данных",
                f"Не удалось получить список таблиц.\n{e}\n\n"
                "Выполните: python migration\\import_from_csv.py",
            )
            return
        if not items:
            self.combo.addItem("(нет таблиц — запустите импорт)", "")
            return
        for it in items:
            name = it.get("name") or ""
            cnt = it.get("row_count", 0)
            self.combo.addItem(f"{name}  ({cnt} строк)", name)

    def _load_rows(self):
        name = self.combo.currentData()
        if not name:
            QMessageBox.information(self, "Таблица", "Выберите таблицу из списка.")
            return
        try:
            payload = self.api.get_access_mirror_data(name)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            return
        cols = payload.get("columns") or []
        rows = payload.get("rows") or []
        self.table.clear()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(rows))
        for ri, row in enumerate(rows):
            for ci, c in enumerate(cols):
                val = row.get(c)
                text = "" if val is None else str(val)
                item = QTableWidgetItem(text)
                item.setToolTip(text[:2000] if len(text) > 200 else text)
                self.table.setItem(ri, ci, item)
        self.table.resizeColumnsToContents()

    def showEvent(self, event):
        super().showEvent(event)
        if self.combo.count() == 0 or (
            self.combo.count() == 1 and self.combo.currentData() == ""
        ):
            self._load_table_list()
