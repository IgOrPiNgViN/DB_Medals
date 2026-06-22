from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QComboBox, QMessageBox, QDialog, QGroupBox, QListWidget, QListWidgetItem,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from api_client import APIError
from ui.voting.protocol import ProtocolDetailDialog
from ui.numeric_sort_item import NumericSortTableItem

THRESHOLD = 0.65
COLOR_PASS = QColor("#C8E6C9")
COLOR_FAIL = QColor("#FFCDD2")


class BallotDialog(QDialog):
    """Бюллетень: выбор вопроса(ов) и голосование кнопками «Да» / «Нет»."""

    def __init__(self, member_name: str, questions: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Бюллетень — {member_name}")
        self.setMinimumSize(560, 440)
        self._questions = list(questions)
        self._votes: dict[int, bool] = {}

        layout = QVBoxLayout(self)
        title = QLabel(f"Голосование: {member_name}")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(title)
        layout.addWidget(QLabel("Выберите вопрос (или несколько), затем нажмите «Да» или «Нет»:"))

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for q in self._questions:
            item = QListWidgetItem(self._question_label(q))
            item.setData(Qt.UserRole, int(q["id"]))
            self._list.addItem(item)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        self._selection_hint = QLabel("Выберите вопрос в списке")
        self._selection_hint.setStyleSheet("color: #666666;")
        layout.addWidget(self._selection_hint)

        vote_row = QHBoxLayout()
        vote_row.addStretch()
        self.btn_yes = QPushButton("Да")
        self.btn_yes.setMinimumWidth(120)
        self.btn_yes.setEnabled(False)
        self.btn_yes.clicked.connect(lambda: self._apply_vote(True))
        vote_row.addWidget(self.btn_yes)
        self.btn_no = QPushButton("Нет")
        self.btn_no.setMinimumWidth(120)
        self.btn_no.setProperty("class", "btn-secondary")
        self.btn_no.setEnabled(False)
        self.btn_no.clicked.connect(lambda: self._apply_vote(False))
        vote_row.addWidget(self.btn_no)
        vote_row.addStretch()
        layout.addLayout(vote_row)

        bottom = QHBoxLayout()
        bottom.addStretch()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setProperty("class", "btn-secondary")
        btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(btn_cancel)
        btn_save = QPushButton("Сохранить голос")
        btn_save.setMinimumWidth(160)
        btn_save.clicked.connect(self._on_save)
        bottom.addWidget(btn_save)
        layout.addLayout(bottom)

        from ui.help_installer import install_help_for_page
        install_help_for_page(self, "ballot_dialog")

        if len(self._questions) == 1:
            self._list.setCurrentRow(0)

    def _question_text(self, q: dict) -> str:
        return (q.get("text") or "").strip() or f"Вопрос #{q['id']}"

    def _question_label(self, q: dict) -> str:
        qid = int(q["id"])
        text = self._question_text(q)
        if qid not in self._votes:
            return text
        mark = "Да" if self._votes[qid] else "Нет"
        return f"{text}  —  {mark}"

    def _refresh_list_labels(self) -> None:
        for row in range(self._list.count()):
            item = self._list.item(row)
            qid = int(item.data(Qt.UserRole))
            q = next((x for x in self._questions if int(x["id"]) == qid), {"id": qid, "text": item.text()})
            item.setText(self._question_label(q))

    def _on_selection_changed(self) -> None:
        selected = self._list.selectedItems()
        enabled = bool(selected)
        self.btn_yes.setEnabled(enabled)
        self.btn_no.setEnabled(enabled)
        if not selected:
            self._selection_hint.setText("Выберите вопрос в списке")
            return
        if len(selected) == 1:
            qid = int(selected[0].data(Qt.UserRole))
            q = next((x for x in self._questions if int(x["id"]) == qid), None)
            text = self._question_text(q) if q else selected[0].text()
            self._selection_hint.setText(f"Выбран вопрос: {text}")
        else:
            self._selection_hint.setText(f"Выбрано вопросов: {len(selected)}")

    def _apply_vote(self, vote_for: bool) -> None:
        selected = self._list.selectedItems()
        if not selected:
            return
        for item in selected:
            self._votes[int(item.data(Qt.UserRole))] = vote_for
        self._refresh_list_labels()
        label = "Да" if vote_for else "Нет"
        self._selection_hint.setText(f"Отмечено: {label}")

    def _on_save(self) -> None:
        missing = [
            self._question_text(q)
            for q in self._questions
            if int(q["id"]) not in self._votes
        ]
        if missing:
            QMessageBox.warning(
                self,
                "Бюллетень",
                "Проголосуйте по всем вопросам бюллетеня.\n\n"
                "Без ответа:\n• " + "\n• ".join(missing[:8])
                + ("\n…" if len(missing) > 8 else ""),
            )
            return
        self.accept()

    def get_votes(self) -> list[dict]:
        """Список {question_id, vote_for} по всем вопросам бюллетеня."""
        return [
            {"question_id": qid, "vote_for": vote_for}
            for qid, vote_for in self._votes.items()
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
        self._decision_popup_shown = False
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
        self.members_table.setSortingEnabled(True)
        self.members_table.horizontalHeader().setSortIndicatorShown(True)
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
        self.results_table.setSortingEnabled(True)
        self.results_table.horizontalHeader().setSortIndicatorShown(True)
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

    def refresh_data(self):
        self._load_bulletins()

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

    def select_bulletin(self, bulletin_id: int):
        """Выбрать бюллетень по ID (переход из мониторинга)."""
        for i, b in enumerate(self._bulletins):
            if b.get("id") == bulletin_id:
                self.bulletin_combo.setCurrentIndex(i)
                return
        self._load_bulletins()
        for i, b in enumerate(self._bulletins):
            if b.get("id") == bulletin_id:
                self.bulletin_combo.setCurrentIndex(i)
                return

    def _on_bulletin_changed(self, idx: int):
        if idx < 0 or idx >= len(self._bulletins):
            self._current_bulletin_id = None
            return
        self._current_bulletin_id = self._bulletins[idx]["id"]
        self._decision_popup_shown = False
        self._load_eligible_members()
        self._load_results()

    def _load_eligible_members(self):
        self.members_table.setSortingEnabled(False)
        self.members_table.setRowCount(0)
        self._eligible_members = []
        if self._current_bulletin_id is None:
            return
        try:
            monitoring = self.api.get_bulletin_monitoring(self._current_bulletin_id)
            self._eligible_members = [
                m for m in monitoring if m.get("is_received", m.get("received"))
            ]
        except APIError:
            return

        for i, entry in enumerate(self._eligible_members):
            self.members_table.insertRow(i)
            no = NumericSortTableItem(str(i + 1), i + 1)
            mid = entry.get("member_id")
            if mid is not None:
                no.setData(Qt.UserRole, int(mid))
            self.members_table.setItem(i, 0, no)
            name = entry.get("member_name", f"ID {entry.get('member_id', '?')}")
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            if mid is not None:
                name_item.setData(Qt.UserRole, int(mid))
            self.members_table.setItem(i, 1, name_item)
            voted = entry.get("has_voted", False)
            status_item = QTableWidgetItem("Проголосовал" if voted else "Ожидание")
            if voted:
                status_item.setBackground(QColor("#C8E6C9"))
            self.members_table.setItem(i, 2, status_item)
        self.members_table.setSortingEnabled(True)

    def _load_results(self, *, show_decision_popup: bool = False):
        self.results_table.setSortingEnabled(False)
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
            self.results_table.setItem(
                i, 0, NumericSortTableItem(question_text, r.get("question_id")),
            )

            pct = r.get("percent_for", 0.0)
            pct_item = NumericSortTableItem(f"{pct:.1f}%", pct)
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
        self.results_table.setSortingEnabled(True)

        if results and all_pass:
            self.lbl_decision.setText("✓ Решение принято (≥65% по всем вопросам)")
            self.lbl_decision.setStyleSheet("color: #2E7D32;")
            if show_decision_popup and not self._decision_popup_shown:
                self._decision_popup_shown = True
                QMessageBox.information(
                    self,
                    "Решение принято",
                    "По всем вопросам бюллетеня набрано не менее 65% голосов «За».",
                )
        elif results:
            self.lbl_decision.setText("✗ Решение не принято — не все вопросы набрали 65%")
            self.lbl_decision.setStyleSheet("color: #C62828;")

    # ── slots ────────────────────────────────────────────────────────────

    def _on_member_double_click(self, index):
        row = index.row()
        it = self.members_table.item(row, 0)
        mid = it.data(Qt.UserRole) if it else None
        if mid is None:
            it = self.members_table.item(row, 1)
            mid = it.data(Qt.UserRole) if it else None
        if mid is None:
            return
        entry = next(
            (e for e in self._eligible_members if e.get("member_id") == int(mid)),
            None,
        )
        if entry is None:
            return
        member_name = entry.get("member_name", "")

        if self._current_bulletin_id is None:
            return
        try:
            data = self.api.get_bulletin_full(self._current_bulletin_id)
            self._questions = []
            for section in data.get("sections", []):
                for q in section.get("questions", []):
                    self._questions.append({
                        "id": q["id"],
                        "text": q.get("question_text", ""),
                    })
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
                    "question_id": v["question_id"],
                    "member_id": member_id,
                    "value": "for" if v["vote_for"] else "against",
                })
            QMessageBox.information(self, "Успех", "Голос записан.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка записи голоса:\n{e}")

        self._load_eligible_members()
        self._load_results(show_decision_popup=True)

    def _on_save_results(self):
        self._load_results()
        QMessageBox.information(self, "Результаты", "Результаты обновлены.")

    def _on_generate_protocol(self):
        if self._current_bulletin_id is None:
            return
        idx = self.bulletin_combo.currentIndex()
        if idx < 0 or idx >= len(self._bulletins):
            return
        b = self._bulletins[idx]
        num = str(b.get("number", self._current_bulletin_id))
        try:
            self.api.create_protocol(
                self._current_bulletin_id,
                {
                    "bulletin_id": self._current_bulletin_id,
                    "number": f"П-{num}",
                },
            )
            QMessageBox.information(self, "Успех", "Протокол сформирован.")
        except APIError as e:
            if e.status_code == 409:
                QMessageBox.information(
                    self,
                    "Протокол",
                    "Для этого бюллетеня протокол уже создан.\n"
                    "Нажмите «Показать протокол» или откройте раздел «Протокол».",
                )
            else:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать протокол:\n{e}")

    def _on_show_protocol(self):
        if self._current_bulletin_id is None:
            return
        try:
            protocols = self.api.get_protocols()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить протоколы:\n{e}")
            return
        proto = next(
            (p for p in protocols if p.get("bulletin_id") == self._current_bulletin_id),
            None,
        )
        if not proto:
            QMessageBox.information(
                self, "Протокол",
                "Сначала нажмите «Сформировать протокол».",
            )
            return
        display = dict(proto)
        try:
            display["results"] = self.api.get_vote_results(self._current_bulletin_id)
        except APIError:
            display["results"] = []
        dlg = ProtocolDetailDialog(display, self)
        dlg.exec_()
