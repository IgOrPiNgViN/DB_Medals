"""Отчёт по этапам жизненного цикла лауреата (ТЗ: сколько на этапе, список)."""

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, pyqtSignal

from api_client import APIError
from ui.print_helpers import print_table, pdf_table

STAGE_LABELS = {
    "nomination": "1. Выдвижение",
    "voting": "2. Голосование",
    "decision": "3. Решение",
    "registration": "4. Оформление",
    "ceremony": "5. Вручение",
    "publication": "6. Опубликование",
    "complete": "Завершён полностью",
}


class LifecycleStagesReportPage(QWidget):
    """Сводка по первому незавершённому этапу ЖЦ для каждой связки лауреат–награда."""

    open_lifecycle = pyqtSignal(int)

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._raw: dict = {}
        self._build_ui()
        self.refresh_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Отчёт: этапы жизненного цикла лауреата")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        hint = QLabel(
            "Каждая строка — связь лауреат–награда. «Текущий этап» — первый незавершённый "
            "этап (или «завершён полностью»)."
        )
        hint.setWordWrap(True)
        hint.setProperty("class", "page-hint")
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Этап:"))
        self.stage_combo = QComboBox()
        self.stage_combo.setMinimumWidth(280)
        self.stage_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self.stage_combo)

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

        self.count_label = QLabel()
        self.count_label.setProperty("class", "section-title")
        layout.addWidget(self.count_label)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["ID связки", "Лауреат", "Награда", "Текущий этап"],
        )
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)

    def refresh_data(self):
        try:
            self._raw = self.api.report_lifecycle_by_stage()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить отчёт:\n{e.detail}")
            self._raw = {}

        self.stage_combo.blockSignals(True)
        self.stage_combo.clear()
        self.stage_combo.addItem("Все этапы", "")
        counts = self._raw.get("counts") or {}
        order = list(STAGE_LABELS.keys())
        for key in order:
            if key not in counts:
                continue
            label = STAGE_LABELS[key]
            n = counts.get(key, 0)
            self.stage_combo.addItem(f"{label} ({n})", key)
        self.stage_combo.blockSignals(False)
        self.stage_combo.setCurrentIndex(0)
        self._apply_filter()

    def _apply_filter(self):
        by_stage = self._raw.get("by_stage") or {}
        counts = self._raw.get("counts") or {}
        key = self.stage_combo.currentData()
        if key == "" or key is None:
            rows = []
            for st in STAGE_LABELS:
                for item in by_stage.get(st, []):
                    rows.append({**item, "_stage": st})
            total = sum(counts.get(k, 0) for k in STAGE_LABELS)
            self.count_label.setText(f"Всего записей: {total}")
        else:
            rows = [{**item, "_stage": key} for item in by_stage.get(key, [])]
            self.count_label.setText(
                f"На этапе «{STAGE_LABELS.get(key, key)}»: {len(rows)}",
            )

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            st = r.get("_stage", "")
            self.table.setItem(i, 0, self._item(str(r.get("laureate_award_id", ""))))
            self.table.setItem(i, 1, self._item(r.get("laureate_name", "")))
            self.table.setItem(i, 2, self._item(r.get("award_name", "")))
            self.table.setItem(i, 3, self._item(STAGE_LABELS.get(st, st)))

    @staticmethod
    def _item(text: str) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        return it

    def _on_double_click(self, index):
        it = self.table.item(index.row(), 0)
        if it and it.text().isdigit():
            self.open_lifecycle.emit(int(it.text()))

    def _on_print(self):
        print_table(self.table, "Отчёт: этапы ЖЦ лауреата", self)

    def _on_pdf(self):
        pdf_table(self.table, "Отчёт: этапы ЖЦ лауреата", self, "lifecycle_stages.pdf")
