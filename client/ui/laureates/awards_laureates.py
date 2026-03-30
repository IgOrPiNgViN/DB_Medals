from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QPushButton, QLabel, QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor

from api_client import APIError
from ui.print_helpers import print_table, pdf_table

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
        self._build_ui()
        self.refresh_data()

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
        layout.addWidget(self.table)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def refresh_data(self):
        try:
            self._report_data = self.api.report_awards_laureates()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить отчёт:\n{e.detail}")
            self._report_data = []

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

        self._apply_filter()

    def _apply_filter(self):
        type_filter = self.award_filter.currentData()
        rows = []
        for award_group in self._report_data:
            if type_filter and award_group.get("award_type") != type_filter:
                continue
            award_name = award_group.get("award_name", "")
            award_type = award_group.get("award_type", "")
            for lau in award_group.get("laureates", []):
                rows.append({
                    "la_id": lau.get("laureate_award_id", ""),
                    "award_name": award_name,
                    "award_type": award_type,
                    "full_name": lau.get("full_name", ""),
                    "category": lau.get("category", ""),
                    "assigned_date": lau.get("assigned_date", ""),
                })

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table.setItem(i, 0, self._make_item(str(r["la_id"])))
            self.table.setItem(i, 1, self._make_item(r["award_name"]))
            self.table.setItem(i, 2, self._make_item(r["award_type"]))
            self.table.setItem(i, 3, self._make_item(r["full_name"]))
            cat = r["category"]
            self.table.setItem(i, 4, self._make_item(CATEGORY_DISPLAY.get(cat, cat or "")))
            self.table.setItem(i, 5, self._make_item(str(r["assigned_date"] or "")))

        self.status_label.setText(f"Строк: {len(rows)}")

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
