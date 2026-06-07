"""Мониторинг согласований наград (ТЗ: раздел НК)."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QPushButton, QLabel, QMessageBox,
    QAbstractItemView, QLineEdit,
)
from PyQt5.QtCore import pyqtSignal, Qt

from api_client import APIError
from ui.print_helpers import print_table, pdf_table
from ui.fetch_worker import run_api_fetch, thread_api_call

APPROVAL_TYPE_FILTER = [
    ("— все типы —", None),
    ("НК", "nk"),
    ("Геральдисты", "heraldists"),
    ("Родственники", "relatives"),
    ("Спонсоры", "sponsors"),
]

APPROVAL_TYPE_RU = {
    "nk": "НК",
    "heraldists": "Геральдисты",
    "relatives": "Родственники",
    "sponsors": "Спонсоры",
}

COLUMNS = [
    ("award_name", "Награда"),
    ("approval_type", "Тип"),
    ("date", "Дата"),
    ("status", "Статус"),
    ("approver_name", "Согласующий"),
    ("details", "Комментарий"),
]


class ApprovalsMonitorPage(QWidget):
    award_selected = pyqtSignal(int)

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._rows: list[dict] = []
        self._refresh_gen = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Мониторинг согласований")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        hint = QLabel(
            "Сводная таблица согласований по всем наградам. "
            "Двойной щелчок по строке — карточка награды."
        )
        hint.setWordWrap(True)
        hint.setProperty("class", "page-hint")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Тип:"))
        self.type_filter = QComboBox()
        self.type_filter.setMinimumWidth(180)
        for label, val in APPROVAL_TYPE_FILTER:
            self.type_filter.addItem(label, val)
        self.type_filter.currentIndexChanged.connect(self.refresh_data)
        toolbar.addWidget(self.type_filter)

        toolbar.addWidget(QLabel("Статус:"))
        self.status_filter = QLineEdit()
        self.status_filter.setPlaceholderText("фильтр по статусу")
        self.status_filter.setMinimumWidth(160)
        self.status_filter.returnPressed.connect(self.refresh_data)
        toolbar.addWidget(self.status_filter)

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
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[1] for c in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        layout.addWidget(self.table, 1)

    def refresh_data(self):
        self._refresh_gen += 1
        gen = self._refresh_gen
        approval_type = self.type_filter.currentData()
        status = self.status_filter.text().strip() or None

        def fetch():
            def load(api):
                return api.report_approvals_monitor(
                    approval_type=approval_type,
                    status=status,
                )
            return thread_api_call(load)

        run_api_fetch(
            fetch,
            on_success=lambda rows: self._on_loaded(rows, gen),
            on_error=lambda err: QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить согласования.\n{err}",
            ),
        )

    def _on_loaded(self, rows: list, gen: int):
        if gen != self._refresh_gen:
            return
        self._rows = rows or []
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            aid = row.get("award_id")
            api_type = row.get("approval_type") or ""
            values = [
                row.get("award_name", ""),
                APPROVAL_TYPE_RU.get(api_type, api_type),
                str(row.get("date") or ""),
                row.get("status", ""),
                row.get("approver_name", ""),
                row.get("details", ""),
            ]
            for col, val in enumerate(values):
                cell = QTableWidgetItem(str(val))
                if aid is not None:
                    cell.setData(Qt.UserRole, int(aid))
                self.table.setItem(i, col, cell)
        self.table.setSortingEnabled(True)

    def _selected_award_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        it = self.table.item(row, 0)
        if it is None:
            return None
        aid = it.data(Qt.UserRole)
        return int(aid) if aid is not None else None

    def _on_double_click(self, index):
        it = self.table.item(index.row(), 0)
        if it is None:
            return
        aid = it.data(Qt.UserRole)
        if aid is not None:
            self.award_selected.emit(int(aid))

    def _on_print(self):
        headers = [c[1] for c in COLUMNS]
        rows = []
        for i in range(self.table.rowCount()):
            rows.append([
                self.table.item(i, c).text() if self.table.item(i, c) else ""
                for c in range(len(COLUMNS))
            ])
        print_table(self, "Мониторинг согласований", headers, rows)

    def _on_pdf(self):
        path, ok = pdf_table(
            self,
            "Мониторинг согласований",
            [c[1] for c in COLUMNS],
            [
                [
                    self.table.item(i, c).text() if self.table.item(i, c) else ""
                    for c in range(len(COLUMNS))
                ]
                for i in range(self.table.rowCount())
            ],
        )
        if ok and path:
            QMessageBox.information(self, "PDF", f"Сохранено:\n{path}")
