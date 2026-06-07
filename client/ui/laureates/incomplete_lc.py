from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QAbstractItemView,
    QGroupBox, QScrollArea, QFileDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush

from api_client import APIError
from ui.numeric_sort_item import NumericSortTableItem
from ui.print_helpers import print_table, pdf_table
from ui.fetch_worker import run_api_fetch, thread_api_call
from ui.table_fill import enable_table_sort_on_click

SECTIONS = [
    ("for_voting", "1. На голосование"),
    ("for_registration", "2. На оформление"),
    ("for_ceremony", "3. На вручение"),
    ("for_publication", "4. На опубликование"),
]

COLS = [
    ("laureate_name", "ФИО"),
    ("award_name", "Награда"),
    ("decision_date", "Присуждение"),
    ("registration_date", "Оформление"),
    ("ceremony_date", "Вручение"),
    ("publication_date", "Опубликование НК"),
    ("publication_smi_web_count", "Сайты СМИ"),
    ("publication_smi_print_count", "Бум. СМИ"),
]

GREEN_BG = QBrush(QColor("#E8F5E9"))


class IncompleteLCPage(QWidget):
    open_lifecycle = pyqtSignal(int)
    open_bulletin = pyqtSignal(str)

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._sections_data: dict = {}
        self._tables: dict[str, QTableWidget] = {}
        self._refresh_gen = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Отчёт: Незавершённый жизненный цикл")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        btn_refresh = QPushButton("Обновить")
        btn_refresh.clicked.connect(self.refresh_data)
        toolbar.addWidget(btn_refresh)
        btn_excel = QPushButton("Выгрузка в Excel…")
        btn_excel.clicked.connect(self._on_excel)
        toolbar.addWidget(btn_excel)
        btn_print = QPushButton("Печать")
        btn_print.clicked.connect(self._on_print)
        toolbar.addWidget(btn_print)
        btn_pdf = QPushButton("В PDF…")
        btn_pdf.setProperty("class", "btn-secondary")
        btn_pdf.clicked.connect(self._on_pdf)
        toolbar.addWidget(btn_pdf)
        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self._sections_layout = QVBoxLayout(inner)
        for key, label in SECTIONS:
            group = QGroupBox(label)
            gl = QVBoxLayout(group)
            table = QTableWidget()
            table.setColumnCount(len(COLS) + 1)
            table.setHorizontalHeaderLabels(["ID"] + [c[1] for c in COLS])
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.verticalHeader().setVisible(False)
            table.doubleClicked.connect(self._on_double_click)
            enable_table_sort_on_click(table)
            gl.addWidget(table)
            if key == "for_voting":
                btn_b = QPushButton("Перейти к бюллетеню (связь с голосованием)")
                btn_b.clicked.connect(self._on_open_bulletin)
                gl.addWidget(btn_b)
            self._tables[key] = table
            self._sections_layout.addWidget(group)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def apply_from_cache_only(self) -> bool:
        return False

    def refresh_data(self):
        self._fetch_from_network()

    def _fetch_from_network(self) -> None:
        self._refresh_gen += 1
        gen = self._refresh_gen

        def fetch():
            return thread_api_call(lambda api: api.report_incomplete_lifecycle_sections())

        run_api_fetch(
            fetch,
            on_success=lambda data: self._on_loaded(data, gen),
            on_error=lambda err: self._on_error(err, gen),
        )

    def _on_loaded(self, data, gen: int):
        if gen != self._refresh_gen:
            return
        self._sections_data = (data or {}).get("sections") or {}
        total = 0
        for key, _ in SECTIONS:
            rows = self._sections_data.get(key) or []
            total += len(rows)
            self._fill_section_table(key, rows)
        self.status_label.setText(f"Всего в очередях: {total}")

    def _on_error(self, err: str, gen: int):
        if gen != self._refresh_gen:
            return
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить отчёт:\n{err}")

    def _fill_section_table(self, key: str, rows: list):
        table = self._tables[key]
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        date_cols = {3, 4, 5, 6}
        for i, row in enumerate(rows):
            la_id = row.get("laureate_award_id", "")
            no_item = NumericSortTableItem(str(la_id), la_id)
            bn = row.get("voting_bulletin_number") or ""
            if bn:
                no_item.setData(Qt.UserRole + 1, str(bn))
            table.setItem(i, 0, no_item)
            for j, (field, _) in enumerate(COLS, start=1):
                val = row.get(field, "")
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if j in date_cols and val:
                    item.setBackground(GREEN_BG)
                table.setItem(i, j, item)
        table.setSortingEnabled(True)

    def _on_open_bulletin(self):
        table = self._tables.get("for_voting")
        if table is None:
            return
        rows = table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self, "Бюллетень",
                "Выберите строку в секции «На голосование».",
            )
            return
        it = table.item(rows[0].row(), 0)
        bn = it.data(Qt.UserRole + 1) if it else None
        if not bn:
            QMessageBox.information(
                self, "Бюллетень",
                "У выбранной связки не указан номер бюллетеня в ЖЦ.",
            )
            return
        self.open_bulletin.emit(str(bn))

    def _on_double_click(self, index):
        table = self.sender()
        if not isinstance(table, QTableWidget):
            return
        it = table.item(index.row(), 0)
        if it and it.text():
            self.open_lifecycle.emit(int(it.text()))

    def _active_table(self) -> QTableWidget | None:
        for table in self._tables.values():
            if table.selectionModel() and table.selectionModel().selectedRows():
                return table
        return self._tables.get("for_voting")

    def _on_excel(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить Excel", "незавершенный_жц.xlsx",
            "Excel (*.xlsx);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            data = self.api.download_incomplete_lifecycle_sections_xlsx()
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Excel", "Файл сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))

    def _on_print(self):
        table = self._active_table()
        if table:
            print_table(table, "Незавершённый жизненный цикл", self)

    def _on_pdf(self):
        table = self._active_table()
        if table:
            pdf_table(table, "Незавершённый жизненный цикл", self, "incomplete_lc.pdf")
