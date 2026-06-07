from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QPushButton, QLabel, QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor

from api_client import APIError
from ui.numeric_sort_item import NumericSortTableItem
from ui.print_helpers import print_table, pdf_table
from ui.fetch_worker import run_api_fetch, thread_api_call
from ui.table_fill import fill_table_batched, enable_table_sort_on_click
from ui.laureates_cache import LaureatesCache

CATEGORY_DISPLAY = {
    "employee": "Сотрудники",
    "veteran": "Ветераны",
    "university": "Университеты",
    "nii": "НИИ",
    "nonprofit": "Некомм. орг.",
    "commercial": "Комм. орг.",
}


class AwardsLaureatesPage(QWidget):
    open_lifecycle = pyqtSignal(int)  # laureate_award_id

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._report_data: list = []
        self._refresh_gen = 0
        self._fill_gen = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Отчёт: Награды — лауреаты")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Тип награды:"))
        self.award_filter = QComboBox()
        self.award_filter.addItem("Все", "")
        self.award_filter.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.award_filter)

        toolbar.addStretch()

        btn_refresh = QPushButton("Обновить")
        btn_refresh.clicked.connect(self.refresh_data)
        toolbar.addWidget(btn_refresh)

        btn_print = QPushButton("Печать")
        btn_print.clicked.connect(self._on_print)
        toolbar.addWidget(btn_print)

        btn_pdf = QPushButton("В PDF…")
        btn_pdf.setProperty("class", "btn-secondary")
        btn_pdf.clicked.connect(self._on_pdf)
        toolbar.addWidget(btn_pdf)

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID связки", "Награда", "Тип награды", "Лауреат", "Категория", "Дата назначения",
        ])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_double_click)
        enable_table_sort_on_click(self.table)
        layout.addWidget(self.table)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def apply_from_cache_only(self) -> bool:
        if LaureatesCache.awards_laureates is None:
            return False
        self._report_data = LaureatesCache.awards_laureates
        self._rebuild_award_filter()
        self._apply_filter()
        return True

    def _rebuild_award_filter(self) -> None:
        award_types = set()
        for award_group in self._report_data:
            at = award_group.get("award_type")
            if at:
                award_types.add(at)
        self.award_filter.blockSignals(True)
        current = self.award_filter.currentData()
        self.award_filter.clear()
        self.award_filter.addItem("Все", "")
        for at in sorted(award_types):
            self.award_filter.addItem(at, at)
        idx = self.award_filter.findData(current)
        self.award_filter.setCurrentIndex(max(idx, 0))
        self.award_filter.blockSignals(False)

    def refresh_data(self):
        if LaureatesCache.awards_laureates is not None and not self._report_data:
            self._report_data = LaureatesCache.awards_laureates
            self._rebuild_award_filter()
            self._apply_filter()
        self._fetch_from_network()

    def _fetch_from_network(self) -> None:
        self._refresh_gen += 1
        gen = self._refresh_gen

        def fetch():
            return thread_api_call(lambda api: api.report_awards_laureates())

        run_api_fetch(
            fetch,
            on_success=lambda data: self._on_report_loaded(data, gen),
            on_error=lambda err: self._on_refresh_error(err, gen),
        )

    def _on_report_loaded(self, data, gen: int):
        if gen != self._refresh_gen:
            return
        LaureatesCache.set_awards_laureates(data)
        self._report_data = data or []
        self._rebuild_award_filter()
        self._apply_filter()

    def _on_refresh_error(self, err: str, gen: int):
        if gen != self._refresh_gen:
            return
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить отчёт:\n{err}")
        self._report_data = []
        self._apply_filter()

    def _apply_filter(self):
        type_filter = self.award_filter.currentData()
        flat = LaureatesCache.awards_laureates_flat
        if flat is None:
            flat = LaureatesCache.flatten_awards_laureates(self._report_data)
        rows = flat if not type_filter else [
            r for r in flat if r.get("award_type") == type_filter
        ]

        self._fill_gen += 1
        fill_gen = self._fill_gen

        def fill_row(table, row, r):
            table.setItem(row, 0, NumericSortTableItem(str(r["la_id"]), r["la_id"]))
            table.setItem(row, 1, self._make_item(r["award_name"]))
            table.setItem(row, 2, self._make_item(r["award_type"]))
            table.setItem(row, 3, self._make_item(r["full_name"]))
            cat = r["category"]
            table.setItem(row, 4, self._make_item(CATEGORY_DISPLAY.get(cat, cat or "")))
            table.setItem(row, 5, self._make_item(str(r["assigned_date"] or "")))

        def done():
            if fill_gen != self._fill_gen:
                return
            self.status_label.setText(f"Строк: {len(rows)}")

        fill_table_batched(
            self.table,
            rows,
            fill_row,
            batch_size=40,
            on_done=done,
            is_cancelled=lambda: fill_gen != self._fill_gen,
        )

    @staticmethod
    def _make_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _on_double_click(self, index):
        row = index.row()
        la_item = self.table.item(row, 0)
        if la_item and la_item.text():
            self.open_lifecycle.emit(int(la_item.text()))

    def _on_print(self):
        print_table(self.table, "Отчёт: Награды — лауреаты", self)

    def _on_pdf(self):
        pdf_table(self.table, "Отчёт: Награды — лауреаты", self, "awards_laureates.pdf")
