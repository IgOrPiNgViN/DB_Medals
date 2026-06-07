from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QPushButton, QLabel, QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush

from api_client import APIError
from ui.numeric_sort_item import NumericSortTableItem
from ui.print_helpers import print_table, pdf_table
from ui.fetch_worker import run_api_fetch, thread_api_call
from ui.laureates_cache import LaureatesCache
from ui.table_fill import fill_table_batched, enable_table_sort_on_click

STAGE_LABELS = {
    "nomination": "Выдвижение",
    "voting": "Голосование",
    "decision": "Решение",
    "registration": "Оформление",
    "consent_pd": "Согласие ПД",
    "ceremony": "Вручение",
    "publication": "Опубликование",
}

ALL_STAGES = list(STAGE_LABELS.keys())

GREEN = QColor("#4CAF50")
RED = QColor("#EF5350")
GREEN_BG = QColor("#E8F5E9")
RED_BG = QColor("#FFEBEE")
GREEN_BRUSH = QBrush(GREEN)
RED_BRUSH = QBrush(RED)
GREEN_BG_BRUSH = QBrush(GREEN_BG)
RED_BG_BRUSH = QBrush(RED_BG)


class IncompleteLCPage(QWidget):
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

        title = QLabel("Отчёт: Незавершённый жизненный цикл")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Незавершённый этап:"))
        self.stage_filter = QComboBox()
        self.stage_filter.addItem("Все", "")
        for key, label in STAGE_LABELS.items():
            self.stage_filter.addItem(label, key)
        self.stage_filter.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.stage_filter)

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
        cols = ["ID связки", "Лауреат", "Награда"] + list(STAGE_LABELS.values()) + ["Причина"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for i in range(3, 3 + len(STAGE_LABELS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(len(cols) - 1, QHeaderView.Stretch)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_double_click)
        enable_table_sort_on_click(self.table)
        layout.addWidget(self.table)

        vote_section = QHBoxLayout()
        vote_label = QLabel("На голосование:")
        vote_label.setProperty("class", "section-title")
        vote_section.addWidget(vote_label)
        self.vote_count_label = QLabel("0")
        vote_section.addWidget(self.vote_count_label)
        vote_section.addStretch()
        layout.addLayout(vote_section)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def apply_from_cache_only(self) -> bool:
        if LaureatesCache.incomplete_lifecycle is None:
            return False
        self._report_data = LaureatesCache.incomplete_lifecycle
        self._apply_filter()
        return True

    def refresh_data(self):
        if LaureatesCache.incomplete_lifecycle is not None and not self._report_data:
            self._report_data = LaureatesCache.incomplete_lifecycle
            self._apply_filter()
        self._fetch_from_network()

    def _fetch_from_network(self) -> None:
        self._refresh_gen += 1
        gen = self._refresh_gen

        def fetch():
            return thread_api_call(lambda api: api.report_incomplete_lifecycle())

        run_api_fetch(
            fetch,
            on_success=lambda data: self._on_report_loaded(data, gen),
            on_error=lambda err: self._on_refresh_error(err, gen),
        )

    def _on_report_loaded(self, data, gen: int):
        if gen != self._refresh_gen:
            return
        LaureatesCache.set_incomplete_lifecycle(data)
        self._report_data = data or []
        self._apply_filter()

    def _on_refresh_error(self, err: str, gen: int):
        if gen != self._refresh_gen:
            return
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить отчёт:\n{err}")
        self._report_data = []
        self._apply_filter()

    def _apply_filter(self):
        stage_filter = self.stage_filter.currentData()
        filtered = self._report_data
        if stage_filter:
            filtered = [
                r for r in filtered
                if stage_filter in r.get("incomplete_stages", [])
                or r.get("reason") == "lifecycle not created"
            ]

        self._fill_gen += 1
        fill_gen = self._fill_gen
        rows = list(filtered)

        def fill_row(table, row_idx, r):
            la_id = r.get("laureate_award_id", "")
            table.setItem(row_idx, 0, NumericSortTableItem(str(la_id), la_id))
            table.setItem(row_idx, 1, self._make_item(r.get("laureate_name", "")))
            table.setItem(row_idx, 2, self._make_item(r.get("award_name", "")))

            incomplete = r.get("incomplete_stages", [])
            reason = r.get("reason", "")

            if reason == "lifecycle not created":
                for col, _ in enumerate(ALL_STAGES):
                    item = QTableWidgetItem("—")
                    item.setBackground(RED_BG_BRUSH)
                    item.setForeground(RED_BRUSH)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row_idx, 3 + col, item)
                reason_item = self._make_item("ЖЦ не создан")
                reason_item.setForeground(RED_BRUSH)
                table.setItem(row_idx, 3 + len(ALL_STAGES), reason_item)
            else:
                for col, stage_key in enumerate(ALL_STAGES):
                    is_incomplete = stage_key in incomplete
                    if is_incomplete:
                        item = QTableWidgetItem("✗")
                        item.setBackground(RED_BG_BRUSH)
                        item.setForeground(RED_BRUSH)
                    else:
                        item = QTableWidgetItem("✓")
                        item.setBackground(GREEN_BG_BRUSH)
                        item.setForeground(GREEN_BRUSH)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    table.setItem(row_idx, 3 + col, item)
                table.setItem(
                    row_idx, 3 + len(ALL_STAGES),
                    self._make_item(", ".join(
                        STAGE_LABELS.get(s, s) for s in incomplete
                    )),
                )

        def done():
            if fill_gen != self._fill_gen:
                return
            vote_count = 0
            for r in rows:
                incomplete = r.get("incomplete_stages", [])
                reason = r.get("reason", "")
                if reason == "lifecycle not created" or "voting" in incomplete:
                    vote_count += 1
            self.vote_count_label.setText(str(vote_count))
            self.status_label.setText(f"Строк: {len(rows)}")

        fill_table_batched(
            self.table,
            rows,
            fill_row,
            batch_size=25,
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
        print_table(self.table, "Отчёт: Незавершённый жизненный цикл", self)

    def _on_pdf(self):
        pdf_table(self.table, "Отчёт: Незавершённый жизненный цикл", self, "incomplete_lc.pdf")
