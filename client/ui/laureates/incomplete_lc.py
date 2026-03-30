from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QPushButton, QLabel, QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush

from api_client import APIError
from ui.print_helpers import print_table, pdf_table

STAGE_LABELS = {
    "nomination": "Выдвижение",
    "voting": "Голосование",
    "decision": "Решение",
    "registration": "Оформление",
    "ceremony": "Вручение",
    "publication": "Опубликование",
}

ALL_STAGES = list(STAGE_LABELS.keys())

GREEN = QColor("#4CAF50")
RED = QColor("#EF5350")
GREEN_BG = QColor("#E8F5E9")
RED_BG = QColor("#FFEBEE")


class IncompleteLCPage(QWidget):
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

    def refresh_data(self):
        try:
            self._report_data = self.api.report_incomplete_lifecycle()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить отчёт:\n{e.detail}")
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

        self.table.setRowCount(len(filtered))
        vote_count = 0
        for row_idx, r in enumerate(filtered):
            la_id = r.get("laureate_award_id", "")
            self.table.setItem(row_idx, 0, self._make_item(str(la_id)))
            self.table.setItem(row_idx, 1, self._make_item(r.get("laureate_name", "")))
            self.table.setItem(row_idx, 2, self._make_item(r.get("award_name", "")))

            incomplete = r.get("incomplete_stages", [])
            reason = r.get("reason", "")

            if reason == "lifecycle not created":
                for col, _ in enumerate(ALL_STAGES):
                    item = QTableWidgetItem("—")
                    item.setBackground(QBrush(RED_BG))
                    item.setForeground(QBrush(RED))
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row_idx, 3 + col, item)
                reason_item = self._make_item("ЖЦ не создан")
                reason_item.setForeground(QBrush(RED))
                self.table.setItem(row_idx, 3 + len(ALL_STAGES), reason_item)
                vote_count += 1
            else:
                for col, stage_key in enumerate(ALL_STAGES):
                    is_incomplete = stage_key in incomplete
                    if is_incomplete:
                        item = QTableWidgetItem("✗")
                        item.setBackground(QBrush(RED_BG))
                        item.setForeground(QBrush(RED))
                    else:
                        item = QTableWidgetItem("✓")
                        item.setBackground(QBrush(GREEN_BG))
                        item.setForeground(QBrush(GREEN))
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row_idx, 3 + col, item)

                if "voting" in incomplete:
                    vote_count += 1

                self.table.setItem(
                    row_idx, 3 + len(ALL_STAGES),
                    self._make_item(", ".join(
                        STAGE_LABELS.get(s, s) for s in incomplete
                    )),
                )

        self.vote_count_label.setText(str(vote_count))
        self.status_label.setText(f"Строк: {len(filtered)}")

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
