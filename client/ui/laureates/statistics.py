from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QDateEdit,
    QAbstractItemView, QGroupBox, QRadioButton, QButtonGroup, QFileDialog,
    QComboBox, QScrollArea,
)
from PyQt5.QtCore import Qt, QDate, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

from api_client import APIError
from ui.fetch_worker import run_api_fetch, thread_api_call
from ui.laureates_cache import LaureatesCache
from ui.table_fill import enable_table_sort_on_click

CATEGORY_DISPLAY = {
    "employee": "Сотрудники",
    "veteran": "Ветераны",
    "university": "Университеты",
    "nii": "НИИ",
    "nonprofit": "Некомм. орг.",
    "commercial": "Комм. орг.",
}

BAR_COLORS = [
    QColor("#1976D2"), QColor("#388E3C"), QColor("#F57C00"),
    QColor("#7B1FA2"), QColor("#D32F2F"), QColor("#00796B"),
]


class BarChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[tuple[str, int]] = []
        self.setMinimumHeight(140)

    def set_data(self, data: list[tuple[str, int]]):
        self._data = data
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        margin_left = 140
        margin_right = 60
        chart_w = w - margin_left - margin_right
        max_val = max((v for _, v in self._data), default=1) or 1
        bar_h = min(24, max(12, (h - 20) // max(len(self._data), 1) - 4))
        gap = 4
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        for i, (label, value) in enumerate(self._data):
            y = 10 + i * (bar_h + gap)
            bar_w = int(chart_w * value / max_val) if max_val > 0 else 0
            color = BAR_COLORS[i % len(BAR_COLORS)]
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(margin_left, y, bar_w, bar_h, 3, 3)
            painter.setPen(QPen(Qt.black))
            painter.drawText(0, y, margin_left - 8, bar_h, Qt.AlignRight | Qt.AlignVCenter, label)
            painter.drawText(margin_left + bar_w + 6, y, margin_right, bar_h, Qt.AlignLeft | Qt.AlignVCenter, str(value))
        painter.end()


class StatisticsPage(QWidget):

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._stats_payload: dict = {}
        self._awards_list: list = []
        self._load_gen = 0
        self._build_ui()
        self._update_period_fields()
        self._load_awards()

    def _load_awards(self):
        try:
            self._awards_list = self.api.get_awards() or []
        except APIError:
            self._awards_list = []
        self.award_filter.blockSignals(True)
        cur = self.award_filter.currentData()
        self.award_filter.clear()
        self.award_filter.addItem("Все награды", None)
        for a in sorted(self._awards_list, key=lambda x: x.get("name", "")):
            self.award_filter.addItem(a.get("name", ""), a.get("id"))
        idx = self.award_filter.findData(cur)
        self.award_filter.setCurrentIndex(max(idx, 0))
        self.award_filter.blockSignals(False)

    def _on_period_changed(self, _button=None):
        self._update_period_fields()
        self._load_data()

    def _update_period_fields(self):
        today = QDate.currentDate()
        checked = self.btn_group.checkedId()
        self.date_from.setEnabled(checked == 3)
        self.date_to.setEnabled(checked == 3)
        if checked == 1:
            self.date_from.setDate(QDate(today.year(), 1, 1))
            self.date_to.setDate(today)
        elif checked == 2:
            self.date_from.setDate(QDate(today.year(), today.month(), 1))
            self.date_to.setDate(today)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Статистика лауреатов")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Награда:"))
        self.award_filter = QComboBox()
        self.award_filter.setMinimumWidth(280)
        self.award_filter.currentIndexChanged.connect(self._load_data)
        filters.addWidget(self.award_filter)
        filters.addStretch()
        layout.addLayout(filters)

        period_group = QGroupBox("Период")
        period_layout = QHBoxLayout(period_group)
        self.btn_group = QButtonGroup(self)
        self.rb_all = QRadioButton("За всё время")
        self.rb_year = QRadioButton("За год")
        self.rb_month = QRadioButton("За месяц")
        self.rb_custom = QRadioButton("Произвольный")
        self.rb_all.setChecked(True)
        for i, rb in enumerate((self.rb_all, self.rb_year, self.rb_month, self.rb_custom)):
            self.btn_group.addButton(rb, i)
            period_layout.addWidget(rb)
        self.btn_group.buttonClicked.connect(self._on_period_changed)

        period_layout.addWidget(QLabel("С:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setEnabled(False)
        period_layout.addWidget(self.date_from)

        period_layout.addWidget(QLabel("По:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setEnabled(False)
        period_layout.addWidget(self.date_to)

        btn_apply = QPushButton("Применить")
        btn_apply.clicked.connect(self._load_data)
        period_layout.addWidget(btn_apply)

        btn_print = QPushButton("Печать")
        btn_print.clicked.connect(self._on_print)
        period_layout.addWidget(btn_print)

        btn_pdf = QPushButton("В PDF…")
        btn_pdf.setProperty("class", "btn-secondary")
        btn_pdf.clicked.connect(self._on_pdf)
        period_layout.addWidget(btn_pdf)

        layout.addWidget(period_group)

        self.total_label = QLabel()
        self.total_label.setProperty("class", "section-title")
        layout.addWidget(self.total_label)

        mid = QHBoxLayout()
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(3)
        self.summary_table.setHorizontalHeaderLabels(["Категория", "Количество", "%"])
        self.summary_table.setMaximumWidth(360)
        self.summary_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        enable_table_sort_on_click(self.summary_table)
        mid.addWidget(self.summary_table)

        self.chart = BarChartWidget()
        mid.addWidget(self.chart, 1)
        layout.addLayout(mid)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.detail_host = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_host)
        scroll.setWidget(self.detail_host)
        layout.addWidget(scroll, 1)

    def refresh_data(self):
        self._load_awards()
        self._load_data()

    def load_data(self):
        self._load_data()

    def apply_from_cache_only(self) -> bool:
        return False

    def _load_data(self):
        self._fetch_from_network()

    def _fetch_from_network(self) -> None:
        self._load_gen += 1
        gen = self._load_gen
        checked = self.btn_group.checkedId()
        from_date = None
        to_date = None
        if checked != 0:
            from_date = self.date_from.date().toPyDate()
            to_date = self.date_to.date().toPyDate()
        award_id = self.award_filter.currentData()

        def fetch():
            return thread_api_call(
                lambda api: api.report_statistics(
                    from_date=from_date,
                    to_date=to_date,
                    award_id=award_id,
                ),
            )

        run_api_fetch(
            fetch,
            on_success=lambda raw: self._on_stats_loaded(raw, gen),
            on_error=lambda err: self._on_load_error(err, gen),
        )

    def _on_stats_loaded(self, raw, gen: int):
        if gen != self._load_gen:
            return
        self._stats_payload = raw if isinstance(raw, dict) else {}
        if self.btn_group.checkedId() == 0 and self.award_filter.currentData() is None:
            LaureatesCache.set_statistics_all(self._stats_payload.get("by_category") or [])
        self._fill_ui()

    def _on_load_error(self, err: str, gen: int):
        if gen != self._load_gen:
            return
        QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить статистику:\n{err}")
        self._stats_payload = {}
        self._fill_ui()

    def _clear_detail(self):
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _make_detail_table(self, rows: list[dict]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["ФИО", "Организация", "Награда"])
        table.setRowCount(len(rows))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        row_h = 28
        table.verticalHeader().setDefaultSectionSize(row_h)
        for i, row in enumerate(rows):
            name = row.get("full_name") or ""
            org = row.get("organization") or ""
            if not org and name:
                org = "—"
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(org))
            table.setItem(i, 2, QTableWidgetItem(row.get("award_name") or ""))
        # Заголовок ~40 px; раньше max-height был слишком мал — строки не были видны.
        header_h = 40
        n = max(len(rows), 1)
        table_h = header_h + row_h * n + 6
        if len(rows) > 10:
            table_h = header_h + row_h * 10 + 6
            table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setMinimumHeight(table_h)
        table.setMaximumHeight(table_h)
        return table

    def _fill_ui(self):
        total = self._stats_payload.get("total") or 0
        self.total_label.setText(f"Общее число лауреатов: {total}")

        by_cat = self._stats_payload.get("by_category") or []
        self.summary_table.setSortingEnabled(False)
        self.summary_table.setRowCount(len(by_cat))
        chart_data: list[tuple[str, int]] = []
        for i, row in enumerate(by_cat):
            cat = row.get("category", "")
            count = row.get("count", 0)
            display = CATEGORY_DISPLAY.get(cat, cat or "Не указана")
            pct = row.get("percent", 0)
            self.summary_table.setItem(i, 0, QTableWidgetItem(display))
            self.summary_table.setItem(i, 1, QTableWidgetItem(str(count)))
            self.summary_table.setItem(i, 2, QTableWidgetItem(f"{pct:.1f}%"))
            chart_data.append((display, count))
        self.summary_table.setSortingEnabled(True)
        self.chart.set_data(chart_data)

        self._clear_detail()
        for group in self._stats_payload.get("groups") or []:
            gbox = QGroupBox(
                f"{group.get('label', '')} — {group.get('count', 0)} "
                f"({group.get('percent_of_total', 0):.1f}% от всех)",
            )
            gl = QVBoxLayout(gbox)
            for sg in group.get("subgroups") or []:
                sg_label = QLabel(
                    f"{sg.get('label', '')}: {sg.get('count', 0)} "
                    f"({sg.get('percent_of_group', 0):.1f}% группы, "
                    f"{sg.get('percent_of_total', 0):.1f}% всего)",
                )
                sg_label.setProperty("class", "section-title")
                gl.addWidget(sg_label)
                gl.addWidget(self._make_detail_table(sg.get("rows") or []))
            self.detail_layout.addWidget(gbox)
        self.detail_layout.addStretch(1)

    def _on_print(self):
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            self.render(painter)
            painter.end()

    def _on_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт в PDF", "", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        painter = QPainter(printer)
        self.render(painter)
        painter.end()
