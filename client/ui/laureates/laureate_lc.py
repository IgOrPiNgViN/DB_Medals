import html as html_module

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QCheckBox, QDateEdit, QLineEdit, QComboBox, QPushButton,
    QLabel, QMessageBox, QScrollArea, QFrame, QMenu, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import pyqtSignal, Qt, QDate, QTimer
from PyQt5.QtGui import QColor, QPalette

from api_client import APIError
from ui.print_helpers import export_html_to_pdf, print_html


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


class ConsentPDWidget(QGroupBox):
    """Согласие на обработку персональных данных."""

    changed = pyqtSignal()

    def __init__(self, api_client, parent=None):
        super().__init__("Согласие на обработку персональных данных", parent)
        self.api = api_client
        self._laureate_award_id: int | None = None
        self._file_info: dict | None = None

        lay = QFormLayout(self)
        lay.setSpacing(6)

        self.sent_date = QDateEdit()
        self.sent_date.setCalendarPopup(True)
        self.sent_date.setSpecialValueText("—")
        self.sent_date.setDate(QDate.fromString("2000-01-01", "yyyy-MM-dd"))
        self.sent_date.dateChanged.connect(self.changed.emit)
        lay.addRow("Дата отправки на подпись:", self.sent_date)

        self.received_date = QDateEdit()
        self.received_date.setCalendarPopup(True)
        self.received_date.setSpecialValueText("—")
        self.received_date.setDate(QDate.fromString("2000-01-01", "yyyy-MM-dd"))
        self.received_date.dateChanged.connect(self.changed.emit)
        lay.addRow("Дата получения:", self.received_date)

        self.received_cb = QCheckBox("Получено")
        self.received_cb.stateChanged.connect(self.changed.emit)
        lay.addRow(self.received_cb)

        self.file_label = QLabel("Файл: —")
        self.file_label.setWordWrap(True)
        lay.addRow("Подписанный файл:", self.file_label)

        btns = QHBoxLayout()
        self.btn_generate = QPushButton("Сформировать согласие…")
        self.btn_generate.clicked.connect(self._on_generate)
        btns.addWidget(self.btn_generate)

        self.btn_attach = QPushButton("Прикрепить файл…")
        self.btn_attach.clicked.connect(self._on_attach)
        btns.addWidget(self.btn_attach)

        self.btn_download = QPushButton("Скачать…")
        self.btn_download.clicked.connect(self._on_download)
        btns.addWidget(self.btn_download)

        self.btn_delete = QPushButton("Удалить файл")
        self.btn_delete.setProperty("class", "btn-danger")
        self.btn_delete.clicked.connect(self._on_delete)
        btns.addWidget(self.btn_delete)

        btns.addStretch()
        lay.addRow(btns)

        self._update_file_controls(False)

    def set_context(self, laureate_award_id: int | None) -> None:
        self._laureate_award_id = laureate_award_id
        self.refresh_file_info()

    def _update_file_controls(self, has_file: bool) -> None:
        self.btn_download.setEnabled(has_file)
        self.btn_delete.setEnabled(has_file)

    def set_values(self, sent: str | None, received: str | None, is_received: bool | None) -> None:
        self._set_date(self.sent_date, sent)
        self._set_date(self.received_date, received)
        self.received_cb.setChecked(bool(is_received))

    def get_values(self) -> dict:
        return {
            "consent_sent_date": self._get_date(self.sent_date),
            "consent_received_date": self._get_date(self.received_date),
            "consent_received": self.received_cb.isChecked(),
        }

    def refresh_file_info(self) -> None:
        self._file_info = None
        if self._laureate_award_id is None:
            self.file_label.setText("Файл: —")
            self._update_file_controls(False)
            return
        try:
            info = self.api.get_consent_file_info(self._laureate_award_id)
        except APIError:
            info = {"exists": False}
        self._file_info = info
        if info.get("exists"):
            self.file_label.setText(f"Файл: {info.get('filename', '—')}")
            self._update_file_controls(True)
        else:
            self.file_label.setText("Файл: —")
            self._update_file_controls(False)

    def _on_attach(self):
        if self._laureate_award_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл согласия", "", "Все файлы (*.*)")
        if not path:
            return
        try:
            self.api.upload_consent_file(self._laureate_award_id, path)
            self.refresh_file_info()
            self.changed.emit()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить файл:\n{e.detail}")

    def _on_download(self):
        if self._laureate_award_id is None:
            return
        filename = "consent.pdf"
        if self._file_info and self._file_info.get("filename"):
            filename = str(self._file_info.get("filename"))
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить файл", filename, "Все файлы (*.*)")
        if not path:
            return
        try:
            data = self.api.download_consent_file(self._laureate_award_id)
            with open(path, "wb") as f:
                f.write(data)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось скачать файл:\n{e.detail}")

    def _on_delete(self):
        if self._laureate_award_id is None:
            return
        try:
            self.api.delete_consent_file(self._laureate_award_id)
            self.refresh_file_info()
            self.changed.emit()
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить файл:\n{e.detail}")

    def _on_generate(self):
        if self._laureate_award_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить сформированное согласие",
            "Согласие ПД.docx",
            "Документ Word (*.docx);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            data = self.api.generate_consent_doc(self._laureate_award_id)
            with open(path, "wb") as f:
                f.write(data)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сформировать согласие:\n{e.detail}")

    @staticmethod
    def _set_date(widget: QDateEdit, date_str: str | None) -> None:
        if date_str:
            d = QDate.fromString(str(date_str), "yyyy-MM-dd")
            if d.isValid():
                widget.setDate(d)
                return
        widget.setDate(QDate.fromString("2000-01-01", "yyyy-MM-dd"))

    @staticmethod
    def _get_date(widget: QDateEdit) -> str | None:
        d = widget.date()
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
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_silent)
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

        self.completeness_group = QGroupBox("Карта завершённости этапов")
        cg_layout = QVBoxLayout(self.completeness_group)
        self.completeness_table = QTableWidget(0, 2)
        self.completeness_table.setHorizontalHeaderLabels(["Этап", "Статус"])
        self.completeness_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.completeness_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.completeness_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.completeness_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.completeness_table.verticalHeader().setVisible(False)
        self.completeness_table.setMaximumHeight(220)
        cg_layout.addWidget(self.completeness_table)
        outer.addWidget(self.completeness_group)

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
        self.stage_consent_pd = ConsentPDWidget(self.api)
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

        self.stage_consent_pd.changed.connect(self._mark_dirty)
        self._stages_layout.insertWidget(4, self.stage_consent_pd)

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

        self.btn_certificate = QPushButton("Удостоверение (черновик)…")
        self.btn_certificate.setProperty("class", "btn-secondary")
        self.btn_certificate.setToolTip(
            "Печать или PDF по данным связки и этапа «Оформление» (шаблон ТЗ).",
        )
        self.btn_certificate.clicked.connect(self._on_certificate_menu)
        btn_row.addWidget(self.btn_certificate)

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
        self.stage_consent_pd.set_context(laureate_award_id)
        try:
            data = self.api.get_laureate_lifecycle(laureate_award_id)
            self._lifecycle_exists = True
            self._populate(data)
        except APIError as e:
            if e.status_code == 404:
                self._lifecycle_exists = False
                self._reset_stages()
                self.stage_consent_pd.set_context(laureate_award_id)
                try:
                    ctx = self.api.get_laureate_award_context(laureate_award_id)
                    bn = (ctx.get("bulletin_number") or "").strip()
                    if bn:
                        w = self.stage_voting.extra_widgets.get("bulletin_number")
                        if isinstance(w, QLineEdit) and not w.text().strip():
                            w.setText(bn)
                except APIError:
                    pass
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
        self.stage_consent_pd.set_values(None, None, False)
        self.stage_consent_pd.refresh_file_info()
        self.btn_reserve.setEnabled(True)
        self.btn_issue.setEnabled(True)
        self.status_label.clear()
        self._refresh_completeness_map(None)

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

        self.stage_consent_pd.set_values(
            data.get("consent_sent_date"),
            data.get("consent_received_date"),
            data.get("consent_received"),
        )
        self.stage_consent_pd.refresh_file_info()

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
        self._refresh_completeness_map(data)

    def _refresh_completeness_map(self, data: dict | None) -> None:
        rows = [
            ("1. Выдвижение", "nomination_done"),
            ("2. Голосование", "voting_done"),
            ("3. Решение", "decision_done"),
            ("4. Оформление", "registration_done"),
            ("Согласие ПД", "consent_received"),
            ("5. Вручение", "ceremony_done"),
            ("6. Опубликование", "publication_done"),
        ]
        self.completeness_table.setRowCount(len(rows))
        for i, (title, key) in enumerate(rows):
            self.completeness_table.setItem(i, 0, QTableWidgetItem(title))
            done = False
            if data is not None:
                if key == "consent_received":
                    done = bool(data.get("consent_received"))
                else:
                    done = bool(data.get(key))
            status = "выполнено" if done else "не выполнено"
            it = QTableWidgetItem(status)
            if done:
                it.setForeground(QColor(46, 125, 50))
            else:
                it.setForeground(QColor(198, 40, 40))
            self.completeness_table.setItem(i, 1, it)

    @staticmethod
    def _set_extra_text(stage: StageWidget, key: str, value):
        w = stage.extra_widgets.get(key)
        if w is None:
            return
        if isinstance(w, QLineEdit):
            w.setText(str(value) if value else "")

    def _mark_dirty(self):
        self._dirty = True
        self._autosave_timer.start(1500)

    def _autosave_silent(self):
        self._on_save(silent=True)

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

        data.update(self.stage_consent_pd.get_values())

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

    def _on_save(self, silent: bool = False):
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
            if not silent:
                QMessageBox.information(self, "Сохранено", "Жизненный цикл обновлён.")
        except APIError as e:
            if not silent:
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

    def _build_certificate_html(self) -> str:
        if self._laureate_award_id is None:
            return ""
        try:
            ctx = self.api.get_laureate_award_context(self._laureate_award_id)
        except APIError:
            ctx = {}
        cert_w = self.stage_registration.extra_widgets.get("certificate_number")
        proto_w = self.stage_decision.extra_widgets.get("protocol_number")
        signer_w = self.stage_registration.extra_widgets.get("signer_id")
        cert = cert_w.text().strip() if isinstance(cert_w, QLineEdit) else ""
        proto = proto_w.text().strip() if isinstance(proto_w, QLineEdit) else ""
        signer = signer_w.currentText() if isinstance(signer_w, QComboBox) else "—"

        parts = [
            "<html><head><meta charset='utf-8'></head><body>",
            "<h2>Удостоверение к награде (черновик для печати)</h2>",
            f"<p><b>Награждается:</b> {html_module.escape(ctx.get('full_name') or '—')}</p>",
            f"<p><b>Награда:</b> {html_module.escape(ctx.get('award_name') or '—')}</p>",
            f"<p><b>Номер удостоверения:</b> {html_module.escape(cert or '—')}</p>",
            f"<p><b>Номер протокола (решение):</b> {html_module.escape(proto or '—')}</p>",
            f"<p><b>Подписант удостоверения:</b> {html_module.escape(signer)}</p>",
            "<hr/><p><i>Форма сформирована из данных жизненного цикла. Подпись и печать — вручную.</i></p>",
            "</body></html>",
        ]
        return "".join(parts)

    def _on_certificate_menu(self):
        if self._laureate_award_id is None:
            return
        menu = QMenu(self)
        menu.addAction("Печать", self._print_certificate)
        menu.addAction("Сохранить PDF…", self._pdf_certificate)
        menu.exec_(self.btn_certificate.mapToGlobal(self.btn_certificate.rect().bottomLeft()))

    def _print_certificate(self):
        html = self._build_certificate_html()
        if html:
            print_html(html, self)

    def _pdf_certificate(self):
        html = self._build_certificate_html()
        if html:
            export_html_to_pdf(html, self, "udostoverenie.pdf")

    def confirm_quit_application(self) -> bool:
        if not self._dirty:
            return True
        # автосохранение перед выходом/переходом
        self._on_save(silent=True)
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "Сохранить изменения?",
            "Имеются несохранённые изменения. Сохранить перед выходом?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Save:
            self._on_save()
        return True

    def _on_back(self):
        if not self.confirm_quit_application():
            return
        self.back_requested.emit()
