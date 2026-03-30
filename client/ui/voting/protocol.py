from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QDialogButtonBox, QTextEdit,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from api_client import APIError
from ui.print_helpers import print_table, pdf_table

COLOR_SIGNED = QColor("#C8E6C9")
COLOR_UNSIGNED = QColor("#FFF9C4")


class ProtocolDetailDialog(QDialog):
    """Dialog showing protocol details."""

    def __init__(self, protocol: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Протокол №{protocol.get('number', '?')}")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        st = str(protocol.get("status", "")).lower()
        signed = st == "signed" or protocol.get("is_signed")
        info_text = (
            f"Номер: {protocol.get('number', '—')}\n"
            f"Дата: {protocol.get('date', '—')}\n"
            f"ID бюллетеня: {protocol.get('bulletin_id', '—')}\n"
            f"Статус: {'Подписан' if signed else 'Не подписан'}\n"
        )
        info = QTextEdit()
        info.setPlainText(info_text)
        info.setReadOnly(True)
        layout.addWidget(info)

        results_label = QLabel("Результаты голосования:")
        results_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(results_label)

        results_text = QTextEdit()
        results_text.setReadOnly(True)
        results_lines = []
        for r in protocol.get("results", []):
            q = r.get("question_text", "Вопрос")
            pct = r.get("percent_for", 0)
            results_lines.append(f"• {q}: {pct:.1f}%")
        results_text.setPlainText("\n".join(results_lines) if results_lines else "Нет данных")
        layout.addWidget(results_text, 1)

        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)


class ProtocolPage(QWidget):
    """Protocols management page."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._protocols: list[dict] = []
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Протоколы")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["№", "Номер", "Дата", "Статус", "Подписан"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_double_click)
        root.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.btn_toggle_signed = QPushButton("Отметить как подписан")
        self.btn_toggle_signed.clicked.connect(self._on_toggle_signed)
        bottom.addWidget(self.btn_toggle_signed)

        self.btn_print = QPushButton("Печать")
        self.btn_print.clicked.connect(self._on_print)
        bottom.addWidget(self.btn_print)

        self.btn_pdf = QPushButton("В PDF…")
        self.btn_pdf.setProperty("class", "btn-secondary")
        self.btn_pdf.clicked.connect(self._on_pdf)
        bottom.addWidget(self.btn_pdf)

        bottom.addStretch()
        root.addLayout(bottom)

    # ── data ─────────────────────────────────────────────────────────────

    def load_data(self):
        try:
            self._protocols = self.api.get_protocols()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить протоколы:\n{e}")
            self._protocols = []

        self.table.setRowCount(0)
        for i, p in enumerate(self._protocols):
            self.table.insertRow(i)
            is_signed = str(p.get("status", "")).lower() == "signed"
            bg = COLOR_SIGNED if is_signed else COLOR_UNSIGNED

            items_data = [
                str(i + 1),
                p.get("number", ""),
                str(p.get("date", "")),
                "Подписан" if is_signed else "Не подписан",
                "☑" if is_signed else "☐",
            ]
            for col, text in enumerate(items_data):
                item = QTableWidgetItem(text)
                item.setBackground(bg)
                if col in (4,):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, col, item)

    # ── slots ────────────────────────────────────────────────────────────

    def _on_double_click(self, index):
        row = index.row()
        if row < 0 or row >= len(self._protocols):
            return
        protocol = dict(self._protocols[row])
        bid = protocol.get("bulletin_id")
        if bid is not None:
            try:
                results = self.api.get_vote_results(bid)
                protocol["results"] = results
            except APIError:
                protocol["results"] = []
        dlg = ProtocolDetailDialog(protocol, self)
        dlg.exec_()

    def _on_toggle_signed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Информация", "Выберите протокол.")
            return
        row = rows[0].row()
        if row < 0 or row >= len(self._protocols):
            return

        protocol = self._protocols[row]
        currently = str(protocol.get("status", "")).lower() == "signed"
        try:
            self.api.update_protocol(
                protocol["id"],
                {"status": "draft" if currently else "signed"},
            )
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить протокол:\n{e}")
            return
        self.load_data()

    def _on_print(self):
        print_table(self.table, "Протоколы", self)

    def _on_pdf(self):
        pdf_table(self.table, "Протоколы", self, "protocols.pdf")
