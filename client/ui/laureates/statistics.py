from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox, QDateEdit,
    QAbstractItemView, QGroupBox, QRadioButton, QButtonGroup,
)
from PyQt5.QtCore import pyqtSignal, Qt, QDate, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog

from api_client import APIError

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
    """Simple horizontal bar chart drawn via QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[tuple[str, int]] = []
        self.setMinimumHeight(180)

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
        margin_top = 10
        margin_bottom = 10
        chart_w = w - margin_left - margin_right
        chart_h = h - margin_top - margin_bottom

        max_val = max((v for _, v in self._data), default=1) or 1
        bar_count = len(self._data)
        bar_h = min(30, max(14, chart_h // max(bar_count, 1) - 4))
        gap = max(4, (chart_h - bar_h * bar_count) // max(bar_count, 1))

        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)

        for i, (label, value) in enumerate(self._data):
            y = margin_top + i * (bar_h + gap)
            bar_w = int(chart_w * value / max_val) if max_val > 0 else 0

            color = BAR_COLORS[i % len(BAR_COLORS)]
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(margin_left, y, bar_w, bar_h, 3, 3)

            painter.setPen(QPen(Qt.black))
            painter.drawText(
                0, y, margin_left - 8, bar_h,
                Qt.AlignRight | Qt.AlignVCenter, label,
            )
            painter.drawText(
                margin_left + bar_w + 6, y, margin_right - 6, bar_h,
                Qt.AlignLeft | Qt.AlignVCenter, str(value),
            )

        painter.end()


class StatisticsPage(QWidget):

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._stats: list = []
        self._build_ui()
        self._on_preset_changed()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Статистика лауреатов")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        period_group = QGroupBox("Период")
        period_layout = QHBoxLayout(period_group)

        self.btn_group = QButtonGroup(self)
        self.rb_year = QRadioButton("За год")
        self.rb_month = QRadioButton("За месяц")
        self.rb_custom = QRadioButton("Произвольный")
        self.rb_all = QRadioButton("За всё время")
        self.rb_all.setChecked(True)
        self.btn_group.addButton(self.rb_all, 0)
        self.btn_group.addButton(self.rb_year, 1)
        self.btn_group.addButton(self.rb_month, 2)
        self.btn_group.addButton(self.rb_custom, 3)
        for rb in (self.rb_all, self.rb_year, self.rb_month, self.rb_custom):
            period_layout.addWidget(rb)
        self.btn_group.buttonClicked.connect(self._on_preset_changed)

        period_layout.addWidget(QLabel("С:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addYears(-1))
        self.date_from.setEnabled(False)
        period_layout.addWidget(self.date_from)

        period_layout.addWidget(QLabel("По:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setEnabled(False)
        period_layout.addWidget(self.date_to)

        btn_apply = QPushButton("Применить")
        btn_apply.setProperty("class", "accent-btn")
        btn_apply.clicked.connect(self._load_data)
        period_layout.addWidget(btn_apply)

        btn_print = QPushButton("Печать")
        btn_print.clicked.connect(self._on_print)
        period_layout.addWidget(btn_print)

        layout.addWidget(period_group)

        mid = QHBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Категория", "Количество", "%"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setMaximumWidth(400)
        mid.addWidget(self.table)

        self.chart = BarChartWidget()
        mid.addWidget(self.chart, 1)

        layout.addLayout(mid, 1)

        self.total_label = QLabel()
        self.total_label.setProperty("class", "section-title")
        layout.addWidget(self.total_label)

    def _on_preset_changed(self):
        today = QDate.currentDate()
        checked = self.btn_group.checkedId()
        custom = (checked == 3)
        self.date_from.setEnabled(custom)
        self.date_to.setEnabled(custom)

        if checked == 1:
            self.date_from.setDate(QDate(today.year(), 1, 1))
            self.date_to.setDate(today)
        elif checked == 2:
            self.date_from.setDate(QDate(today.year(), today.month(), 1))
            self.date_to.setDate(today)

        self._load_data()

    def _load_data(self):
        checked = self.btn_group.checkedId()
        from_date = None
        to_date = None
        if checked != 0:
            from_date = self.date_from.date().toPyDate()
            to_date = self.date_to.date().toPyDate()

        try:
            self._stats = self.api.report_statistics(from_date=from_date, to_date=to_date)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить статистику:\n{e.detail}")
            self._stats = []

        if isinstance(self._stats, dict):
            self._stats = self._stats.get("data", []) or []

        self._fill_table()

    def _fill_table(self):
        total = sum(r.get("count", 0) for r in self._stats)
        self.table.setRowCount(len(self._stats))
        chart_data: list[tuple[str, int]] = []

        for i, row in enumerate(self._stats):
            cat = row.get("category", "")
            count = row.get("count", 0)
            display = CATEGORY_DISPLAY.get(cat, cat or "Не указана")
            pct = (count / total * 100) if total else 0

            self.table.setItem(i, 0, self._make_item(display))
            self.table.setItem(i, 1, self._make_item(str(count)))
            self.table.setItem(i, 2, self._make_item(f"{pct:.1f}%"))
            chart_data.append((display, count))

        self.chart.set_data(chart_data)
        self.total_label.setText(f"Всего лауреатов: {total}")

    @staticmethod
    def _make_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _on_print(self):
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec_() == QPrintDialog.Accepted:
            painter = QPainter(printer)
            self.render(painter)
            painter.end()
