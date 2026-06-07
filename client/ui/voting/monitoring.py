from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QCheckBox, QDateEdit, QDialogButtonBox,
    QFormLayout, QGroupBox, QScrollArea, QFileDialog,
)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from api_client import APIError
from ui.print_helpers import print_table, pdf_table

COLOR_RECEIVED = QColor("#C8E6C9")
COLOR_NOT_RECEIVED = QColor("#FFCDD2")
COLOR_NOT_SENT = QColor("#E0E0E0")


class DetailedMonitoringDialog(QDialog):
    """Detailed view of bulletin distribution for a single bulletin."""

    def __init__(
        self,
        bulletin_id: int,
        bulletin_label: str,
        monitoring_data: list,
        api_client,
        parent_page=None,
        parent=None,
    ):
        super().__init__(parent)
        self.api = api_client
        self._bulletin_id = bulletin_id
        self._parent_page = parent_page
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
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_mark_sent = QPushButton("Отметить отправлено")
        self.btn_mark_sent.clicked.connect(lambda: self._mark_selected(sent=True))
        btn_row.addWidget(self.btn_mark_sent)

        self.btn_mark_received = QPushButton("Отметить получено")
        self.btn_mark_received.clicked.connect(lambda: self._mark_selected(received=True))
        btn_row.addWidget(self.btn_mark_received)

        btn_row.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self._populate()

    def _reload_from_server(self) -> bool:
        try:
            self._monitoring = self.api.get_bulletin_monitoring(self._bulletin_id)
        except APIError as e:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось обновить данные:\n{e.detail}",
            )
            return False
        if self._parent_page is not None:
            self._parent_page.refresh_bulletin_monitoring(self._bulletin_id, self._monitoring)
        return True

    def _populate(self, selected_dist_ids: set[int] | None = None):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for i, entry in enumerate(self._monitoring):
            self.table.insertRow(i)
            name = entry.get("member_name", f"ID {entry.get('member_id', '?')}")
            # API может отдавать sent/received или is_sent/is_received
            sent = entry.get("is_sent", entry.get("sent", False))
            received = entry.get("is_received", entry.get("received", False))

            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem("Да" if sent else "Нет"))
            self.table.setItem(i, 2, QTableWidgetItem(entry.get("sent_date", "—")))
            self.table.setItem(i, 3, QTableWidgetItem("Да" if received else "Нет"))
            self.table.setItem(i, 4, QTableWidgetItem(entry.get("received_date", "—")))
            dist_id = entry.get("distribution_id")
            if dist_id is not None:
                self.table.item(i, 0).setData(Qt.UserRole, int(dist_id))

            if received:
                color = COLOR_RECEIVED
            elif sent:
                color = COLOR_NOT_RECEIVED
            else:
                color = COLOR_NOT_SENT
            for c in range(5):
                self.table.item(i, c).setBackground(color)

            if selected_dist_ids and dist_id is not None and int(dist_id) in selected_dist_ids:
                self.table.selectRow(i)

        self.table.setSortingEnabled(True)

    def _mark_selected(self, sent: bool = False, received: bool = False):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Мониторинг", "Выберите строку.")
            return
        today = QDate.currentDate().toString("yyyy-MM-dd")
        updated_ids: set[int] = set()
        for r in rows:
            row = r.row()
            id_item = self.table.item(row, 0)
            if not id_item:
                continue
            dist_id = id_item.data(Qt.UserRole)
            if not dist_id:
                continue
            payload = {}
            if sent:
                payload["sent"] = True
                payload["sent_date"] = today
            if received:
                payload["received"] = True
                payload["received_date"] = today
            try:
                self.api.update_distribution(int(dist_id), payload)
                updated_ids.add(int(dist_id))
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось обновить рассылку:\n{e.detail}")
                return
        if updated_ids and self._reload_from_server():
            self._populate(selected_dist_ids=updated_ids)


class MonitoringPage(QWidget):
    """Monitoring page showing response status for all bulletins."""

    enter_results_requested = pyqtSignal(int)  # bulletin_id

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._bulletins: list[dict] = []
        self._members: list[dict] = []
        self._monitoring_cache: dict[int, list] = {}
        self._summary_cache: dict[int, dict] = {}
        self._quorum_bulletin_id: int | None = None
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

        self.quorum_label = QLabel("")
        self.quorum_label.setWordWrap(True)
        root.addWidget(self.quorum_label)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()

        self.btn_enter_results = QPushButton("Внести результаты голосования")
        self.btn_enter_results.setEnabled(False)
        self.btn_enter_results.setStyleSheet("background-color: #9E9E9E; color: white;")
        self.btn_enter_results.clicked.connect(self._on_enter_results)
        bottom.addWidget(self.btn_enter_results)

        self.btn_show_monitoring = QPushButton("Обновить")
        self.btn_show_monitoring.clicked.connect(self.load_data)
        bottom.addWidget(self.btn_show_monitoring)

        self.btn_print = QPushButton("Печать")
        self.btn_print.clicked.connect(self._on_print)
        bottom.addWidget(self.btn_print)

        self.btn_pdf = QPushButton("В PDF…")
        self.btn_pdf.setProperty("class", "btn-secondary")
        self.btn_pdf.clicked.connect(self._on_pdf)
        bottom.addWidget(self.btn_pdf)

        self.btn_docx = QPushButton("Word (DOCX)…")
        self.btn_docx.setProperty("class", "btn-secondary")
        self.btn_docx.clicked.connect(self._on_monitoring_docx)
        bottom.addWidget(self.btn_docx)

        bottom.addStretch()
        root.addLayout(bottom)

    # ── data ─────────────────────────────────────────────────────────────

    def refresh_data(self):
        self.load_data()

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
        self._summary_cache.clear()
        for b in self._bulletins:
            try:
                summary = self.api.get_bulletin_monitoring_summary(b["id"])
                self._summary_cache[b["id"]] = summary
                self._monitoring_cache[b["id"]] = summary.get("entries") or []
            except APIError:
                try:
                    self._monitoring_cache[b["id"]] = self.api.get_bulletin_monitoring(b["id"])
                except APIError:
                    self._monitoring_cache[b["id"]] = []
                self._summary_cache[b["id"]] = {}

        self._build_matrix()

    def refresh_bulletin_monitoring(self, bulletin_id: int, monitoring: list | None = None):
        """Обновить кэш и матрицу для одного бюллетеня (без полной перезагрузки страницы)."""
        if monitoring is not None:
            self._monitoring_cache[bulletin_id] = monitoring
        else:
            try:
                self._monitoring_cache[bulletin_id] = self.api.get_bulletin_monitoring(
                    bulletin_id,
                )
            except APIError:
                return
        self._build_matrix()

    def _build_matrix(self):
        n_members = len(self._members)
        n_bulletins = len(self._bulletins)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(n_members)
        self.table.setColumnCount(n_bulletins + 1)

        headers = ["Член НК"]
        for b in self._bulletins:
            mon = self._monitoring_cache.get(b["id"], [])
            received = sum(1 for m in mon if m.get("is_received", m.get("received")))
            total = len(mon)
            headers.append(f"Б-{b.get('number', '?')} ({received} из {total})")
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        member_index = {m["id"]: i for i, m in enumerate(self._members)}

        for row, m in enumerate(self._members):
            name_item = QTableWidgetItem(m.get("full_name", ""))
            self.table.setItem(row, 0, name_item)

        self._quorum_bulletin_id = None
        quorum_parts: list[str] = []
        any_quorum = False
        for col_idx, b in enumerate(self._bulletins):
            summary = self._summary_cache.get(b["id"], {})
            required = summary.get("required_received")
            received_total = summary.get("received_count")
            if required is not None and received_total is not None:
                quorum_parts.append(
                    f"Б-{b.get('number', '?')}: получено {received_total}, нужно {required}",
                )
                if summary.get("quorum_met"):
                    any_quorum = True
                    if self._quorum_bulletin_id is None:
                        self._quorum_bulletin_id = b["id"]

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
                elif entry.get("is_received", entry.get("received")):
                    item.setText("✓")
                    item.setBackground(QBrush(COLOR_RECEIVED))
                    received_count += 1
                    total_sent += 1
                else:
                    item.setText("✗")
                    item.setBackground(QBrush(COLOR_NOT_RECEIVED))
                    total_sent += 1

                self.table.setItem(row, col_idx + 1, item)

        if quorum_parts:
            self.quorum_label.setText("Кворум 65%: " + "  |  ".join(quorum_parts))
        else:
            self.quorum_label.setText("")

        self.table.setSortingEnabled(True)
        self._update_results_button(any_quorum)

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
        dlg = DetailedMonitoringDialog(
            b["id"], label, mon, self.api, parent_page=self, parent=self,
        )
        dlg.exec_()

    def _on_enter_results(self):
        if self._quorum_bulletin_id is None:
            QMessageBox.information(
                self, "Результаты",
                "Кворум 65% ещё не достигнут ни по одному бюллетеню.",
            )
            return
        self.enter_results_requested.emit(int(self._quorum_bulletin_id))

    def _on_print(self):
        print_table(self.table, "Мониторинг ответов", self)

    def _on_pdf(self):
        pdf_table(self.table, "Мониторинг ответов", self, "monitoring.pdf")

    def _on_monitoring_docx(self):
        if self._quorum_bulletin_id is None:
            QMessageBox.information(self, "DOCX", "Нет бюллетеня с достигнутым кворумом.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить мониторинг", "monitoring.docx", "Word (*.docx)",
        )
        if not path:
            return
        try:
            data = self.api.download_bulletin_monitoring_docx(int(self._quorum_bulletin_id))
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Сохранено", f"Файл сохранён:\n{path}")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать DOCX:\n{e.detail}")
