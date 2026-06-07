from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QPushButton, QLabel, QMessageBox,
    QAbstractItemView, QFileDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt

from api_client import APIError
from ui.print_helpers import print_table, pdf_table
from ui.fetch_worker import run_api_fetch, thread_api_call
from ui.table_fill import fill_table_batched, enable_table_sort_on_click
from ui.laureates_cache import LaureatesCache

TZ_COLUMNS = [
    ("full_name", "ФИО"),
    ("position", "Должность"),
    ("organization", "Организация"),
    ("protocol_number", "№ протокола"),
    ("protocol_date", "Дата проток."),
    ("handed_over", "Вруч."),
]


class AwardsLaureatesPage(QWidget):
    open_lifecycle = pyqtSignal(int)

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
        toolbar.addWidget(QLabel("Награда:"))
        self.award_filter = QComboBox()
        self.award_filter.setMinimumWidth(320)
        self.award_filter.addItem("— выберите награду —", None)
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

        btn_excel = QPushButton("Выгрузка в Excel…")
        btn_excel.clicked.connect(self._on_excel)
        toolbar.addWidget(btn_excel)

        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(len(TZ_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in TZ_COLUMNS])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        for col in range(3, len(TZ_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

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
        current = self.award_filter.currentData()
        self.award_filter.blockSignals(True)
        self.award_filter.clear()
        self.award_filter.addItem("— выберите награду —", None)
        for group in self._report_data:
            aid = group.get("award_id")
            name = group.get("award_name", f"#{aid}")
            if aid is not None:
                self.award_filter.addItem(name, int(aid))
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

    def _rows_for_filter(self) -> list[dict]:
        award_id = self.award_filter.currentData()
        if award_id is None:
            return []
        for group in self._report_data:
            if group.get("award_id") == award_id:
                rows = []
                for lau in group.get("laureates") or []:
                    rows.append({
                        "laureate_award_id": lau.get("laureate_award_id"),
                        "full_name": lau.get("full_name", ""),
                        "position": lau.get("position") or "",
                        "organization": lau.get("organization") or "",
                        "protocol_number": lau.get("protocol_number") or "",
                        "protocol_date": str(lau.get("protocol_date") or ""),
                        "handed_over": "Да" if lau.get("handed_over") else "Нет",
                    })
                return rows
        return []

    def _apply_filter(self):
        rows = self._rows_for_filter()
        self._fill_gen += 1
        fill_gen = self._fill_gen

        def fill_row(table, row, r):
            for col, (field, _) in enumerate(TZ_COLUMNS):
                text = str(r.get(field, ""))
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col == 0:
                    la_id = r.get("laureate_award_id")
                    if la_id is not None:
                        item.setData(Qt.UserRole, int(la_id))
                table.setItem(row, col, item)

        def done():
            if fill_gen != self._fill_gen:
                return
            award_name = self.award_filter.currentText()
            if self.award_filter.currentData() is None:
                self.status_label.setText("Выберите награду в списке")
            else:
                self.status_label.setText(f"{award_name}: строк {len(rows)}")

        fill_table_batched(
            self.table,
            rows,
            fill_row,
            batch_size=40,
            on_done=done,
            is_cancelled=lambda: fill_gen != self._fill_gen,
        )

    def _on_double_click(self, index):
        it = self.table.item(index.row(), 0)
        if it is None:
            return
        la_id = it.data(Qt.UserRole)
        if la_id is not None:
            self.open_lifecycle.emit(int(la_id))

    def _on_print(self):
        print_table(self.table, "Отчёт: Награды — лауреаты", self)

    def _on_pdf(self):
        pdf_table(self.table, "Отчёт: Награды — лауреаты", self, "awards_laureates.pdf")

    def _on_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить Excel", "награды_лауреаты.xlsx",
            "Excel (*.xlsx);;Все файлы (*.*)",
        )
        if not path:
            return
        award_id = self.award_filter.currentData()
        try:
            data = self.api.download_awards_laureates_xlsx(
                award_id=int(award_id) if award_id is not None else None,
            )
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Excel", "Файл сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))
