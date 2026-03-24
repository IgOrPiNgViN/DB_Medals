from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QCheckBox, QDateEdit, QDialogButtonBox,
    QFormLayout, QGroupBox, QScrollArea,
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QColor, QBrush

from api_client import APIError

COLOR_RECEIVED = QColor("#C8E6C9")
COLOR_NOT_RECEIVED = QColor("#FFCDD2")
COLOR_NOT_SENT = QColor("#E0E0E0")


class DetailedMonitoringDialog(QDialog):
    """Detailed view of bulletin distribution for a single bulletin."""

    def __init__(self, bulletin_label: str, monitoring_data: list, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._monitoring = monitoring_data
        self.setWindowTitle(f"Мониторинг — {bulletin_label}")
        self.setMinimumSize(560, 450)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Член НК", "Отправлено", "Дата отправки", "Получено", "Дата получения",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table, 1)

        self._populate()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _populate(self):
        self.table.setRowCount(0)
        for i, entry in enumerate(self._monitoring):
            self.table.insertRow(i)
            name = entry.get("member_name", f"ID {entry.get('member_id', '?')}")
            sent = entry.get("is_sent", False)
            received = entry.get("is_received", False)

            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem("Да" if sent else "Нет"))
            self.table.setItem(i, 2, QTableWidgetItem(entry.get("sent_date", "—")))
            self.table.setItem(i, 3, QTableWidgetItem("Да" if received else "Нет"))
            self.table.setItem(i, 4, QTableWidgetItem(entry.get("received_date", "—")))

            if received:
                color = COLOR_RECEIVED
            elif sent:
                color = COLOR_NOT_RECEIVED
            else:
                color = COLOR_NOT_SENT
            for c in range(5):
                self.table.item(i, c).setBackground(color)


class MonitoringPage(QWidget):
    """Monitoring page showing response status for all bulletins."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._bulletins: list[dict] = []
        self._members: list[dict] = []
        self._monitoring_cache: dict[int, list] = {}
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Мониторинг ответов")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        legend = QHBoxLayout()
        for color, text in [
            ("#C8E6C9", "Получен"),
            ("#FFCDD2", "Не получен"),
            ("#E0E0E0", "Не отправлен"),
        ]:
            box = QLabel("  ")
            box.setFixedSize(18, 18)
            box.setStyleSheet(f"background-color: {color}; border: 1px solid #999;")
            legend.addWidget(box)
            legend.addWidget(QLabel(text))
            legend.addSpacing(12)
        legend.addStretch()
        root.addLayout(legend)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.doubleClicked.connect(self._on_double_click)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()

        self.btn_enter_results = QPushButton("Внести результаты голосования")
        self.btn_enter_results.setEnabled(False)
        self.btn_enter_results.setStyleSheet("background-color: #9E9E9E; color: white;")
        self.btn_enter_results.clicked.connect(self._on_enter_results)
        bottom.addWidget(self.btn_enter_results)

        self.btn_show_monitoring = QPushButton("Показать мониторинг")
        self.btn_show_monitoring.clicked.connect(self.load_data)
        bottom.addWidget(self.btn_show_monitoring)

        self.btn_print = QPushButton("Печать")
        self.btn_print.clicked.connect(
            lambda: QMessageBox.information(self, "Печать", "Функция печати будет реализована позднее."),
        )
        bottom.addWidget(self.btn_print)

        bottom.addStretch()
        root.addLayout(bottom)

    # ── data ─────────────────────────────────────────────────────────────

    def load_data(self):
        try:
            self._bulletins = self.api.get_bulletins()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить бюллетени:\n{e}")
            self._bulletins = []

        try:
            self._members = self.api.get_committee_members()
        except APIError:
            self._members = []

        self._monitoring_cache.clear()
        for b in self._bulletins:
            try:
                self._monitoring_cache[b["id"]] = self.api.get_bulletin_monitoring(b["id"])
            except APIError:
                self._monitoring_cache[b["id"]] = []

        self._build_matrix()

    def _build_matrix(self):
        n_members = len(self._members)
        n_bulletins = len(self._bulletins)

        self.table.setRowCount(n_members)
        self.table.setColumnCount(n_bulletins + 1)

        headers = ["Член НК"]
        for b in self._bulletins:
            mon = self._monitoring_cache.get(b["id"], [])
            received = sum(1 for m in mon if m.get("is_received"))
            total = len(mon)
            headers.append(f"Б-{b.get('number', '?')} ({received} из {total})")
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        member_index = {m["id"]: i for i, m in enumerate(self._members)}

        for row, m in enumerate(self._members):
            name_item = QTableWidgetItem(m.get("full_name", ""))
            self.table.setItem(row, 0, name_item)

        all_received_enough = True
        for col_idx, b in enumerate(self._bulletins):
            mon = self._monitoring_cache.get(b["id"], [])
            lookup = {entry.get("member_id"): entry for entry in mon}

            received_count = 0
            total_sent = 0
            for row, m in enumerate(self._members):
                entry = lookup.get(m["id"])
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignCenter)

                if entry is None:
                    item.setText("—")
                    item.setBackground(QBrush(COLOR_NOT_SENT))
                elif entry.get("is_received"):
                    item.setText("✓")
                    item.setBackground(QBrush(COLOR_RECEIVED))
                    received_count += 1
                    total_sent += 1
                else:
                    item.setText("✗")
                    item.setBackground(QBrush(COLOR_NOT_RECEIVED))
                    total_sent += 1

                self.table.setItem(row, col_idx + 1, item)

            if total_sent > 0 and received_count < total_sent:
                all_received_enough = False

        self._update_results_button(all_received_enough and n_bulletins > 0)

    def _update_results_button(self, enabled: bool):
        self.btn_enter_results.setEnabled(enabled)
        if enabled:
            self.btn_enter_results.setStyleSheet("background-color: #4CAF50; color: white;")
        else:
            self.btn_enter_results.setStyleSheet("background-color: #9E9E9E; color: white;")

    # ── slots ────────────────────────────────────────────────────────────

    def _on_double_click(self, index):
        col = index.column()
        if col < 1 or col - 1 >= len(self._bulletins):
            return
        b = self._bulletins[col - 1]
        mon = self._monitoring_cache.get(b["id"], [])
        label = f"Бюллетень №{b.get('number', '?')}"
        dlg = DetailedMonitoringDialog(label, mon, self.api, self)
        dlg.exec_()

    def _on_enter_results(self):
        QMessageBox.information(
            self, "Результаты",
            "Переход к подсчёту голосов.",
        )
