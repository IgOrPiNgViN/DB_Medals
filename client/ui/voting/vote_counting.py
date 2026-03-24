from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QMessageBox, QDialog, QDialogButtonBox,
    QCheckBox, QGroupBox, QScrollArea,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from api_client import APIError

THRESHOLD = 0.65
COLOR_PASS = QColor("#C8E6C9")
COLOR_FAIL = QColor("#FFCDD2")


class BallotDialog(QDialog):
    """Ballot form: list of questions with 'За' checkboxes."""

    def __init__(self, member_name: str, questions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Бюллетень — {member_name}")
        self.setMinimumSize(520, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Голосование: {member_name}"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._q_layout = QVBoxLayout(container)

        self._checkboxes: list[tuple[int, QCheckBox]] = []
        for q in questions:
            text = q.get("text", f"Вопрос #{q['id']}")
            cb = QCheckBox(text)
            cb.setChecked(True)
            self._q_layout.addWidget(cb)
            self._checkboxes.append((q["id"], cb))
        self._q_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_votes(self) -> list[dict]:
        """Return list of {question_id, vote_for}."""
        return [
            {"question_id": qid, "vote_for": cb.isChecked()}
            for qid, cb in self._checkboxes
        ]


class VoteCountingPage(QWidget):
    """Vote counting page with 65% threshold logic."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._bulletins: list[dict] = []
        self._current_bulletin_id: int | None = None
        self._questions: list[dict] = []
        self._eligible_members: list[dict] = []
        self._build_ui()
        self._load_bulletins()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)

        title = QLabel("Подсчёт голосов")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        root.addWidget(title)

        selector = QHBoxLayout()
        selector.addWidget(QLabel("Протокол / Бюллетень:"))
        self.bulletin_combo = QComboBox()
        self.bulletin_combo.currentIndexChanged.connect(self._on_bulletin_changed)
        selector.addWidget(self.bulletin_combo, 1)
        selector.addStretch()
        root.addLayout(selector)

        # ── members who received the bulletin ───────────────────────────
        members_group = QGroupBox("Члены НК (получившие бюллетень)")
        mg_layout = QVBoxLayout(members_group)

        self.members_table = QTableWidget()
        self.members_table.setColumnCount(3)
        self.members_table.setHorizontalHeaderLabels(["№", "ФИО", "Статус"])
        self.members_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.members_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.members_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.members_table.doubleClicked.connect(self._on_member_double_click)
        mg_layout.addWidget(self.members_table)

        btn_save = QPushButton("Сохранить результаты")
        btn_save.clicked.connect(self._on_save_results)
        mg_layout.addWidget(btn_save, alignment=Qt.AlignLeft)
        root.addWidget(members_group)

        # ── results display ─────────────────────────────────────────────
        results_group = QGroupBox("Результаты голосования")
        rg_layout = QVBoxLayout(results_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Вопрос", "% За", "Решение"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        rg_layout.addWidget(self.results_table)

        self.lbl_decision = QLabel("")
        self.lbl_decision.setFont(QFont("Segoe UI", 12, QFont.Bold))
        rg_layout.addWidget(self.lbl_decision)

        res_btns = QHBoxLayout()
        self.btn_generate_protocol = QPushButton("Сформировать протокол")
        self.btn_generate_protocol.clicked.connect(self._on_generate_protocol)
        res_btns.addWidget(self.btn_generate_protocol)

        self.btn_show_protocol = QPushButton("Показать протокол")
        self.btn_show_protocol.clicked.connect(self._on_show_protocol)
        res_btns.addWidget(self.btn_show_protocol)

        res_btns.addStretch()
        rg_layout.addLayout(res_btns)
        root.addWidget(results_group)

    # ── data loading ─────────────────────────────────────────────────────

    def _load_bulletins(self):
        self.bulletin_combo.blockSignals(True)
        self.bulletin_combo.clear()
        try:
            self._bulletins = self.api.get_bulletins()
        except APIError:
            self._bulletins = []

        for b in self._bulletins:
            self.bulletin_combo.addItem(f"Бюллетень №{b.get('number', '?')}", b["id"])
        self.bulletin_combo.blockSignals(False)

        if self._bulletins:
            self._on_bulletin_changed(0)

    def _on_bulletin_changed(self, idx: int):
        if idx < 0 or idx >= len(self._bulletins):
            self._current_bulletin_id = None
            return
        self._current_bulletin_id = self._bulletins[idx]["id"]
        self._load_eligible_members()
        self._load_results()

    def _load_eligible_members(self):
        self.members_table.setRowCount(0)
        self._eligible_members = []
        if self._current_bulletin_id is None:
            return
        try:
            monitoring = self.api.get_bulletin_monitoring(self._current_bulletin_id)
            self._eligible_members = [
                m for m in monitoring if m.get("is_received")
            ]
        except APIError:
            return

        for i, entry in enumerate(self._eligible_members):
            self.members_table.insertRow(i)
            self.members_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            name = entry.get("member_name", f"ID {entry.get('member_id', '?')}")
            self.members_table.setItem(i, 1, QTableWidgetItem(name))
            voted = entry.get("has_voted", False)
            status_item = QTableWidgetItem("Проголосовал" if voted else "Ожидание")
            if voted:
                status_item.setBackground(QColor("#C8E6C9"))
            self.members_table.setItem(i, 2, status_item)

    def _load_results(self):
        self.results_table.setRowCount(0)
        self.lbl_decision.setText("")
        if self._current_bulletin_id is None:
            return

        try:
            results = self.api.get_vote_results(self._current_bulletin_id)
        except APIError:
            return

        all_pass = True
        for i, r in enumerate(results):
            self.results_table.insertRow(i)

            question_text = r.get("question_text", f"Вопрос #{r.get('question_id', '?')}")
            self.results_table.setItem(i, 0, QTableWidgetItem(question_text))

            pct = r.get("percent_for", 0.0)
            pct_item = QTableWidgetItem(f"{pct:.1f}%")
            pct_item.setTextAlignment(Qt.AlignCenter)

            passed = pct >= THRESHOLD * 100
            if not passed:
                all_pass = False

            color = COLOR_PASS if passed else COLOR_FAIL
            decision_text = "Принято" if passed else "Не принято"

            pct_item.setBackground(color)
            self.results_table.setItem(i, 1, pct_item)

            dec_item = QTableWidgetItem(decision_text)
            dec_item.setBackground(color)
            dec_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(i, 2, dec_item)

        if results and all_pass:
            self.lbl_decision.setText("✓ Решение принято (≥65% по всем вопросам)")
            self.lbl_decision.setStyleSheet("color: #2E7D32;")
        elif results:
            self.lbl_decision.setText("✗ Решение не принято — не все вопросы набрали 65%")
            self.lbl_decision.setStyleSheet("color: #C62828;")

    # ── slots ────────────────────────────────────────────────────────────

    def _on_member_double_click(self, index):
        row = index.row()
        if row < 0 or row >= len(self._eligible_members):
            return
        entry = self._eligible_members[row]
        member_name = entry.get("member_name", "")

        if self._current_bulletin_id is None:
            return
        try:
            bulletin = self.api.get_bulletin(self._current_bulletin_id)
            self._questions = []
            for section in bulletin.get("sections", []):
                self._questions.extend(section.get("questions", []))
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить вопросы:\n{e}")
            return

        if not self._questions:
            QMessageBox.information(self, "Информация", "В бюллетене нет вопросов.")
            return

        dlg = BallotDialog(member_name, self._questions, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        votes = dlg.get_votes()
        member_id = entry.get("member_id")
        try:
            for v in votes:
                self.api.record_vote(v["question_id"], {
                    "member_id": member_id,
                    "vote_for": v["vote_for"],
                })
            QMessageBox.information(self, "Успех", "Голос записан.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка записи голоса:\n{e}")

        self._load_eligible_members()
        self._load_results()

    def _on_save_results(self):
        self._load_results()
        QMessageBox.information(self, "Результаты", "Результаты обновлены.")

    def _on_generate_protocol(self):
        if self._current_bulletin_id is None:
            return
        try:
            self.api.create_protocol(self._current_bulletin_id, {})
            QMessageBox.information(self, "Успех", "Протокол сформирован.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать протокол:\n{e}")

    def _on_show_protocol(self):
        QMessageBox.information(
            self, "Протокол",
            "Детальный просмотр протокола будет реализован позднее.",
        )
