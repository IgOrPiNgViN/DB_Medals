from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QCheckBox, QDateEdit, QLineEdit, QComboBox, QPushButton,
    QLabel, QMessageBox, QScrollArea, QFrame,
)
from PyQt5.QtCore import pyqtSignal, Qt, QDate
from PyQt5.QtGui import QColor, QPalette

from api_client import APIError


class StageWidget(QGroupBox):
    """Single lifecycle-stage block with a done checkbox, date, and extra fields."""

    changed = pyqtSignal()

    def __init__(self, title: str, extra_fields: list[tuple[str, str, str]], parent=None):
        super().__init__(title, parent)
        self._layout = QFormLayout(self)
        self._layout.setSpacing(6)

        self.done_cb = QCheckBox("Выполнено")
        self.done_cb.stateChanged.connect(self._on_changed)
        self._layout.addRow(self.done_cb)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setSpecialValueText("—")
        self.date_edit.setDate(QDate.fromString("2000-01-01", "yyyy-MM-dd"))
        self.date_edit.dateChanged.connect(self._on_changed)
        self._layout.addRow("Дата:", self.date_edit)

        self.extra_widgets: dict[str, QWidget] = {}
        for field_key, field_label, widget_type in extra_fields:
            if widget_type == "line":
                w = QLineEdit()
                w.textChanged.connect(self._on_changed)
            elif widget_type == "combo":
                w = QComboBox()
                w.currentIndexChanged.connect(self._on_changed)
            else:
                w = QLineEdit()
                w.textChanged.connect(self._on_changed)
            self.extra_widgets[field_key] = w
            self._layout.addRow(f"{field_label}:", w)

        self._update_indicator()

    def _on_changed(self):
        self._update_indicator()
        self.changed.emit()

    def _update_indicator(self):
        if self.done_cb.isChecked():
            self.setStyleSheet(
                "StageWidget { border: 2px solid #4CAF50; border-radius: 6px; "
                "background-color: #E8F5E9; }"
            )
        else:
            self.setStyleSheet(
                "StageWidget { border: 2px solid #EF5350; border-radius: 6px; "
                "background-color: #FFEBEE; }"
            )

    def set_done(self, done: bool):
        self.done_cb.setChecked(done)

    def set_date(self, date_str: str | None):
        if date_str:
            d = QDate.fromString(str(date_str), "yyyy-MM-dd")
            if d.isValid():
                self.date_edit.setDate(d)
                return
        self.date_edit.setDate(QDate.fromString("2000-01-01", "yyyy-MM-dd"))

    def get_date(self) -> str | None:
        d = self.date_edit.date()
        if d == QDate.fromString("2000-01-01", "yyyy-MM-dd"):
            return None
        return d.toString("yyyy-MM-dd")


class LaureateLifecyclePage(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._laureate_award_id: int | None = None
        self._lifecycle_exists = False
        self._dirty = False
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 18, 24, 18)

        top_bar = QHBoxLayout()
        btn_back = QPushButton("← Назад")
        btn_back.clicked.connect(self._on_back)
        top_bar.addWidget(btn_back)

        self.title_label = QLabel("Жизненный цикл лауреата")
        self.title_label.setProperty("class", "page-title")
        top_bar.addWidget(self.title_label, 1)
        outer.addLayout(top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        self._stages_layout = QVBoxLayout(content)
        self._stages_layout.setSpacing(12)

        self.stage_nomination = StageWidget("1. Выдвижение", [
            ("initiator", "Инициатор", "line"),
        ])
        self.stage_voting = StageWidget("2. Голосование", [
            ("bulletin_number", "Номер бюллетеня", "line"),
        ])
        self.stage_decision = StageWidget("3. Решение", [
            ("protocol_number", "Номер протокола", "line"),
        ])
        self.stage_registration = StageWidget("4. Оформление", [
            ("signer_id", "Подписант", "combo"),
            ("certificate_number", "Номер удостоверения", "line"),
        ])
        self.stage_ceremony = StageWidget("5. Вручение", [
            ("place", "Место вручения", "line"),
        ])
        self.stage_publication = StageWidget("6. Опубликование", [
            ("source", "Источник", "line"),
        ])

        self._all_stages = [
            self.stage_nomination, self.stage_voting, self.stage_decision,
            self.stage_registration, self.stage_ceremony, self.stage_publication,
        ]
        for s in self._all_stages:
            s.changed.connect(self._mark_dirty)
            self._stages_layout.addWidget(s)

        self._load_signer_combo()

        self._stages_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        btn_row = QHBoxLayout()

        self.btn_reserve = QPushButton("Учесть присуждение (резерв)")
        self.btn_reserve.clicked.connect(self._on_reserve)
        btn_row.addWidget(self.btn_reserve)

        self.btn_issue = QPushButton("Учесть вручение (списание)")
        self.btn_issue.clicked.connect(self._on_issue)
        btn_row.addWidget(self.btn_issue)

        btn_row.addStretch()

        btn_save = QPushButton("Сохранить")
        btn_save.setProperty("class", "accent-btn")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        outer.addLayout(btn_row)

        self.status_label = QLabel()
        outer.addWidget(self.status_label)

    def _load_signer_combo(self):
        combo: QComboBox = self.stage_registration.extra_widgets["signer_id"]
        combo.clear()
        combo.addItem("— не выбран —", None)
        try:
            members = self.api.get_committee_members(is_active=True)
            for m in members:
                label = m.get("full_name", f"#{m['id']}")
                combo.addItem(label, m["id"])
        except APIError:
            pass

    def load_lifecycle(self, laureate_award_id: int):
        self._laureate_award_id = laureate_award_id
        self.title_label.setText(f"Жизненный цикл — связка #{laureate_award_id}")
        try:
            data = self.api.get_laureate_lifecycle(laureate_award_id)
            self._lifecycle_exists = True
            self._populate(data)
        except APIError as e:
            if e.status_code == 404:
                self._lifecycle_exists = False
                self._reset_stages()
                self.status_label.setText("Жизненный цикл ещё не создан. Заполните и сохраните.")
            else:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить ЖЦ:\n{e.detail}")
        self._dirty = False

    def _reset_stages(self):
        for s in self._all_stages:
            s.set_done(False)
            s.set_date(None)
            for w in s.extra_widgets.values():
                if isinstance(w, QLineEdit):
                    w.clear()
                elif isinstance(w, QComboBox):
                    w.setCurrentIndex(0)
        self.btn_reserve.setEnabled(True)
        self.btn_issue.setEnabled(True)
        self.status_label.clear()

    def _populate(self, data: dict):
        self.stage_nomination.set_done(data.get("nomination_done", False))
        self.stage_nomination.set_date(data.get("nomination_date"))
        self._set_extra_text(self.stage_nomination, "initiator", data.get("nomination_initiator"))

        self.stage_voting.set_done(data.get("voting_done", False))
        self.stage_voting.set_date(data.get("voting_date"))
        self._set_extra_text(self.stage_voting, "bulletin_number", data.get("voting_bulletin_number"))

        self.stage_decision.set_done(data.get("decision_done", False))
        self.stage_decision.set_date(data.get("decision_date"))
        self._set_extra_text(self.stage_decision, "protocol_number", data.get("decision_protocol_number"))

        self.stage_registration.set_done(data.get("registration_done", False))
        self.stage_registration.set_date(data.get("registration_date"))
        self._set_extra_text(self.stage_registration, "certificate_number", data.get("registration_certificate_number"))
        combo: QComboBox = self.stage_registration.extra_widgets["signer_id"]
        signer = data.get("registration_signer_id")
        if signer is not None:
            idx = combo.findData(signer)
            combo.setCurrentIndex(max(idx, 0))
        else:
            combo.setCurrentIndex(0)

        self.stage_ceremony.set_done(data.get("ceremony_done", False))
        self.stage_ceremony.set_date(data.get("ceremony_date"))
        self._set_extra_text(self.stage_ceremony, "place", data.get("ceremony_place"))

        self.stage_publication.set_done(data.get("publication_done", False))
        self.stage_publication.set_date(data.get("publication_date"))
        self._set_extra_text(self.stage_publication, "source", data.get("publication_source"))

        reserved = data.get("inventory_reserved", False)
        issued = data.get("inventory_issued", False)
        self.btn_reserve.setEnabled(not reserved)
        self.btn_issue.setEnabled(not issued)
        parts = []
        if reserved:
            parts.append("Присуждение учтено (резерв)")
        if issued:
            parts.append("Вручение учтено (списание)")
        self.status_label.setText("  |  ".join(parts) if parts else "")

    @staticmethod
    def _set_extra_text(stage: StageWidget, key: str, value):
        w = stage.extra_widgets.get(key)
        if w is None:
            return
        if isinstance(w, QLineEdit):
            w.setText(str(value) if value else "")

    def _mark_dirty(self):
        self._dirty = True

    def _collect_data(self) -> dict:
        data: dict = {}
        if self._laureate_award_id is not None:
            data["laureate_award_id"] = self._laureate_award_id

        data["nomination_done"] = self.stage_nomination.done_cb.isChecked()
        data["nomination_date"] = self.stage_nomination.get_date()
        data["nomination_initiator"] = self._get_extra_text(self.stage_nomination, "initiator")

        data["voting_done"] = self.stage_voting.done_cb.isChecked()
        data["voting_date"] = self.stage_voting.get_date()
        data["voting_bulletin_number"] = self._get_extra_text(self.stage_voting, "bulletin_number")

        data["decision_done"] = self.stage_decision.done_cb.isChecked()
        data["decision_date"] = self.stage_decision.get_date()
        data["decision_protocol_number"] = self._get_extra_text(self.stage_decision, "protocol_number")

        data["registration_done"] = self.stage_registration.done_cb.isChecked()
        data["registration_date"] = self.stage_registration.get_date()
        data["registration_certificate_number"] = self._get_extra_text(
            self.stage_registration, "certificate_number",
        )
        combo: QComboBox = self.stage_registration.extra_widgets["signer_id"]
        signer = combo.currentData()
        data["registration_signer_id"] = signer if signer else None

        data["ceremony_done"] = self.stage_ceremony.done_cb.isChecked()
        data["ceremony_date"] = self.stage_ceremony.get_date()
        data["ceremony_place"] = self._get_extra_text(self.stage_ceremony, "place")

        data["publication_done"] = self.stage_publication.done_cb.isChecked()
        data["publication_date"] = self.stage_publication.get_date()
        data["publication_source"] = self._get_extra_text(self.stage_publication, "source")

        return data

    @staticmethod
    def _get_extra_text(stage: StageWidget, key: str) -> str | None:
        w = stage.extra_widgets.get(key)
        if w is None:
            return None
        if isinstance(w, QLineEdit):
            val = w.text().strip()
            return val or None
        return None

    def _on_save(self):
        if self._laureate_award_id is None:
            return
        data = self._collect_data()
        try:
            if self._lifecycle_exists:
                result = self.api.update_laureate_lifecycle(self._laureate_award_id, data)
            else:
                result = self.api.create_laureate_lifecycle(self._laureate_award_id, data)
                self._lifecycle_exists = True
            self._populate(result)
            self._dirty = False
            QMessageBox.information(self, "Сохранено", "Жизненный цикл обновлён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить ЖЦ:\n{e.detail}")

    def _on_reserve(self):
        if self._laureate_award_id is None:
            return
        reply = QMessageBox.question(
            self, "Учесть присуждение",
            "Пометить экземпляр награды как зарезервированный?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            data = {"inventory_reserved": True}
            if self._lifecycle_exists:
                result = self.api.update_laureate_lifecycle(self._laureate_award_id, data)
            else:
                data["laureate_award_id"] = self._laureate_award_id
                result = self.api.create_laureate_lifecycle(self._laureate_award_id, data)
                self._lifecycle_exists = True
            self._populate(result)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось учесть присуждение:\n{e.detail}")

    def _on_issue(self):
        if self._laureate_award_id is None:
            return
        reply = QMessageBox.question(
            self, "Учесть вручение",
            "Пометить экземпляр награды как выданный (списание)?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            data = {"inventory_issued": True}
            if self._lifecycle_exists:
                result = self.api.update_laureate_lifecycle(self._laureate_award_id, data)
            else:
                data["laureate_award_id"] = self._laureate_award_id
                result = self.api.create_laureate_lifecycle(self._laureate_award_id, data)
                self._lifecycle_exists = True
            self._populate(result)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось учесть вручение:\n{e.detail}")

    def _on_back(self):
        if self._dirty:
            reply = QMessageBox.question(
                self, "Сохранить изменения?",
                "Имеются несохранённые изменения. Сохранить перед выходом?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                self._on_save()
            elif reply == QMessageBox.Cancel:
                return
        self.back_requested.emit()
