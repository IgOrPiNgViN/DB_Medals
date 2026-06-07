"""Отчёт «Награды — бюллетени»: связки по номеру бюллетеня."""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QPushButton, QLabel, QMessageBox,
    QAbstractItemView, QSplitter,
)
from PyQt5.QtCore import pyqtSignal, Qt

from api_client import APIError
from ui.numeric_sort_item import NumericSortTableItem
from ui.print_helpers import print_table, pdf_table
from ui.fetch_worker import run_api_fetch, thread_api_call

DETAIL_COLUMNS = [
    ("laureate_name", "Лауреат"),
    ("award_name", "Награда"),
    ("assigned_date", "Дата назначения"),
]


class AwardsBulletinsPage(QWidget):
    open_lifecycle = pyqtSignal(int)
    open_bulletin = pyqtSignal(str)

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._groups: list[dict] = []
        self._refresh_gen = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Отчёт: Награды — бюллетени")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        hint = QLabel(
            "Связки лауреат–награда по номеру бюллетеня из жизненного цикла. "
            "Двойной щелчок по детали — ЖЦ лауреата; по номеру бюллетеня — модуль «Бюллетени»."
        )
        hint.setWordWrap(True)
        hint.setProperty("class", "page-hint")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Бюллетень:"))
        self.bn_filter = QComboBox()
        self.bn_filter.setMinimumWidth(280)
        self.bn_filter.addItem("— все —", None)
        self.bn_filter.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.bn_filter)

        toolbar.addStretch()

        btn_refresh = QPushButton("Обновить")
        btn_refresh.clicked.connect(self.refresh_data)
        toolbar.addWidget(btn_refresh)

        btn_bulletin = QPushButton("Открыть бюллетень")
        btn_bulletin.clicked.connect(self._on_open_bulletin)
        toolbar.addWidget(btn_bulletin)

        btn_print = QPushButton("Печать")
        btn_print.clicked.connect(self._on_print)
        toolbar.addWidget(btn_print)

        btn_pdf = QPushButton("В PDF…")
        btn_pdf.setProperty("class", "btn-secondary")
        btn_pdf.clicked.connect(self._on_pdf)
        toolbar.addWidget(btn_pdf)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Vertical)

        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Номер бюллетеня", "Связок"])
        self.summary_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.summary_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.currentCellChanged.connect(self._on_summary_row_changed)
        self.summary_table.doubleClicked.connect(self._on_summary_double_click)
        splitter.addWidget(self.summary_table)

        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(len(DETAIL_COLUMNS))
        self.detail_table.setHorizontalHeaderLabels([c[1] for c in DETAIL_COLUMNS])
        self.detail_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.horizontalHeader().setStretchLastSection(True)
        self.detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.detail_table.doubleClicked.connect(self._on_detail_double_click)
        splitter.addWidget(self.detail_table)

        splitter.setSizes([220, 400])
        layout.addWidget(splitter, 1)

    def refresh_data(self):
        self._refresh_gen += 1
        gen = self._refresh_gen

        def fetch():
            def load(api):
                return api.report_awards_by_bulletin()
            return thread_api_call(load)

        run_api_fetch(
            fetch,
            on_success=lambda data: self._on_loaded(data, gen),
            on_error=lambda err: QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить отчёт.\n{err}",
            ),
        )

    def _on_loaded(self, data: dict, gen: int):
        if gen != self._refresh_gen:
            return
        self._groups = data.get("groups") or []

        prev_bn = self.bn_filter.currentData()
        self.bn_filter.blockSignals(True)
        self.bn_filter.clear()
        self.bn_filter.addItem("— все —", None)
        for g in self._groups:
            bn = g.get("bulletin_number", "")
            self.bn_filter.addItem(f"{bn} ({g.get('count', 0)})", bn)
        if prev_bn:
            idx = self.bn_filter.findData(prev_bn)
            if idx >= 0:
                self.bn_filter.setCurrentIndex(idx)
        self.bn_filter.blockSignals(False)

        self.summary_table.setRowCount(len(self._groups))
        for i, g in enumerate(self._groups):
            bn = g.get("bulletin_number", "")
            self.summary_table.setItem(i, 0, QTableWidgetItem(bn))
            cnt = g.get("count", 0)
            self.summary_table.setItem(i, 1, NumericSortTableItem(str(cnt), cnt))

        self._apply_filter()

    def _current_group_items(self) -> list[dict]:
        bn = self.bn_filter.currentData()
        if bn:
            for g in self._groups:
                if g.get("bulletin_number") == bn:
                    return g.get("items") or []
            return []
        items: list[dict] = []
        for g in self._groups:
            items.extend(g.get("items") or [])
        return items

    def _apply_filter(self):
        items = self._current_group_items()
        self.detail_table.setRowCount(len(items))
        for i, row in enumerate(items):
            la_id = row.get("laureate_award_id")
            for col, (key, _label) in enumerate(DETAIL_COLUMNS):
                val = str(row.get(key) or "")
                cell = QTableWidgetItem(val)
                if col == 0 and la_id is not None:
                    cell.setData(Qt.UserRole, int(la_id))
                self.detail_table.setItem(i, col, cell)

    def _on_summary_row_changed(self, row, _col, _prow, _pcol):
        if row < 0 or row >= len(self._groups):
            return
        bn = self._groups[row].get("bulletin_number")
        idx = self.bn_filter.findData(bn)
        if idx >= 0:
            self.bn_filter.setCurrentIndex(idx)

    def _on_summary_double_click(self, index):
        if index.row() < 0 or index.row() >= len(self._groups):
            return
        bn = self._groups[index.row()].get("bulletin_number")
        if bn:
            self.open_bulletin.emit(str(bn))

    def _on_detail_double_click(self, index):
        it = self.detail_table.item(index.row(), 0)
        if it is None:
            return
        la_id = it.data(Qt.UserRole)
        if la_id is not None:
            self.open_lifecycle.emit(int(la_id))

    def _on_open_bulletin(self):
        bn = self.bn_filter.currentData()
        if not bn:
            QMessageBox.information(self, "Бюллетень", "Выберите номер бюллетеня.")
            return
        self.open_bulletin.emit(str(bn))

    def _on_print(self):
        headers = ["Бюллетень", "Лауреат", "Награда", "Дата"]
        rows = []
        for g in self._groups:
            bn = g.get("bulletin_number", "")
            for item in g.get("items") or []:
                rows.append([
                    bn,
                    item.get("laureate_name", ""),
                    item.get("award_name", ""),
                    str(item.get("assigned_date") or ""),
                ])
        print_table(self, "Награды — бюллетени", headers, rows)

    def _on_pdf(self):
        headers = ["Бюллетень", "Лауреат", "Награда", "Дата"]
        rows = []
        for g in self._groups:
            bn = g.get("bulletin_number", "")
            for item in g.get("items") or []:
                rows.append([
                    bn,
                    item.get("laureate_name", ""),
                    item.get("award_name", ""),
                    str(item.get("assigned_date") or ""),
                ])
        path, ok = pdf_table(self, "Награды — бюллетени", headers, rows)
        if ok and path:
            QMessageBox.information(self, "PDF", f"Сохранено:\n{path}")
