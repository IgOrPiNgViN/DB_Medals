from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QPushButton,
    QLabel, QTextEdit, QMessageBox, QAbstractItemView, QGroupBox,
    QProgressBar, QFileDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QColor, QBrush

from api_client import APIError
from ui.connection_state import connection_state
from ui.offline_guard import (
    save_local_draft_on_failure,
    user_facing_error,
    warn_if_offline,
)
from ui.numeric_sort_item import NumericSortTableItem
from ui.table_fill import configure_table_rows
from ui.photo_helpers import make_photo_preview_label, set_photo_bytes, set_photo_placeholder, wrap_photo_row
from ui.form_helpers import make_form_label, configure_form, make_scroll_page

CATEGORIES = [
    ("employee", "Сотрудники"),
    ("veteran", "Ветераны"),
    ("university", "Университеты"),
    ("nii", "НИИ"),
    ("nonprofit", "Некомм. орг."),
    ("commercial", "Комм. орг."),
]

CATEGORY_DISPLAY = dict(CATEGORIES)

LIFECYCLE_STAGES = [
    "nomination_done", "voting_done", "decision_done",
    "registration_done", "ceremony_done", "publication_done",
]


class LaureateDetailPage(QWidget):
    back_requested = pyqtSignal()
    open_lifecycle = pyqtSignal(int)  # laureate_award_id

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._laureate_id: int | None = None
        self._original_data: dict = {}
        self._dirty = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_silent)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        top_bar = QHBoxLayout()
        btn_back = QPushButton("← Назад")
        btn_back.clicked.connect(self._on_back)
        top_bar.addWidget(btn_back)

        self.title_label = QLabel("Карточка лауреата")
        self.title_label.setProperty("class", "page-title")
        top_bar.addWidget(self.title_label, 1)

        btn_delete = QPushButton("Удалить")
        btn_delete.setStyleSheet("color: #D32F2F;")
        btn_delete.clicked.connect(self._on_delete)
        top_bar.addWidget(btn_delete)
        layout.addLayout(top_bar)

        info_group = QGroupBox("Основные данные")
        form = QFormLayout(info_group)
        configure_form(form)
        fl = make_form_label

        self.full_name = QLineEdit()
        self.full_name.textChanged.connect(self._mark_dirty)
        form.addRow(fl("ФИО:"), self.full_name)

        self.category = QComboBox()
        self.category.addItem("— не указана —", "")
        for val, label in CATEGORIES:
            self.category.addItem(label, val)
        self.category.currentIndexChanged.connect(self._mark_dirty)
        form.addRow(fl("Категория:"), self.category)

        self.position = QLineEdit()
        self.position.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Должность:"), self.position)

        self.organization = QLineEdit()
        self.organization.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Организация:"), self.organization)

        self.phone = QLineEdit()
        self.phone.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Телефон:"), self.phone)

        self.email = QLineEdit()
        self.email.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Email:"), self.email)

        self.address = QLineEdit()
        self.address.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Адрес:"), self.address)

        self.birth_date = QLineEdit()
        self.birth_date.setPlaceholderText("ГГГГ-ММ-ДД")
        self.birth_date.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Дата рождения:"), self.birth_date)

        self.passport = QLineEdit()
        self.passport.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Паспорт:"), self.passport)

        self.inn = QLineEdit()
        self.inn.textChanged.connect(self._mark_dirty)
        form.addRow(fl("ИНН:"), self.inn)

        self.snils = QLineEdit()
        self.snils.textChanged.connect(self._mark_dirty)
        form.addRow(fl("СНИЛС:"), self.snils)

        self.regalia = QTextEdit()
        self.regalia.setMaximumHeight(60)
        self.regalia.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Регалии:"), self.regalia)

        self.photo_label = make_photo_preview_label(120, 150)
        btn_photo = QPushButton("Загрузить фото…")
        btn_photo.clicked.connect(self._on_upload_photo)
        photo_widget = wrap_photo_row(self.photo_label, btn_photo)
        form.addRow(fl("Фотография:"), photo_widget)

        self.notes = QTextEdit()
        self.notes.setMinimumHeight(60)
        self.notes.setMaximumHeight(100)
        self.notes.textChanged.connect(self._mark_dirty)
        form.addRow(fl("Примечания:"), self.notes)

        btn_save = QPushButton("Сохранить")
        btn_save.setProperty("class", "accent-btn")
        btn_save.clicked.connect(self._on_save)
        form.addRow("", btn_save)

        layout.addWidget(info_group)

        monitor_label = QLabel("Мониторинг наград лауреата")
        monitor_label.setProperty("class", "section-title")
        layout.addWidget(monitor_label)

        self.monitor_table = QTableWidget()
        self.monitor_table.setColumnCount(7)
        self.monitor_table.setHorizontalHeaderLabels([
            "Награда", "Выдвиж.", "Соглас.", "Присужд.", "Оформ.", "Вруч.", "Опубл.",
        ])
        self.monitor_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.monitor_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.monitor_table.verticalHeader().setVisible(False)
        configure_table_rows(self.monitor_table, 36)
        layout.addWidget(self.monitor_table)

        awards_label = QLabel("Привязанные награды")
        awards_label.setProperty("class", "section-title")
        layout.addWidget(awards_label)

        self.awards_table = QTableWidget()
        self.awards_table.setColumnCount(5)
        self.awards_table.setHorizontalHeaderLabels([
            "ID связки", "Награда (ID)", "Дата назначения", "Статус", "Прогресс ЖЦ",
        ])
        header = self.awards_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)

        self.awards_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.awards_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.awards_table.verticalHeader().setVisible(False)
        configure_table_rows(self.awards_table, 40)
        self.awards_table.doubleClicked.connect(self._on_award_double_click)
        self.awards_table.setSortingEnabled(True)
        self.awards_table.horizontalHeader().setSortIndicatorShown(True)
        layout.addWidget(self.awards_table)

        extracts_label = QLabel("Выписки из протоколов")
        extracts_label.setProperty("class", "section-title")
        layout.addWidget(extracts_label)

        extracts_bar = QHBoxLayout()
        self.btn_download_extract = QPushButton("Скачать Word (DOCX)")
        self.btn_download_extract.clicked.connect(self._on_download_extract)
        extracts_bar.addWidget(self.btn_download_extract)
        extracts_bar.addStretch()
        layout.addLayout(extracts_bar)

        self.extracts_table = QTableWidget()
        self.extracts_table.setColumnCount(4)
        self.extracts_table.setHorizontalHeaderLabels([
            "Связка", "Дата выписки", "Примечание", "ID выписки",
        ])
        self.extracts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.extracts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.extracts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.extracts_table.verticalHeader().setVisible(False)
        configure_table_rows(self.extracts_table, 36)
        self.extracts_table.doubleClicked.connect(self._on_extract_double_click)
        layout.addWidget(self.extracts_table)

        layout.addStretch()
        content.setMinimumWidth(640)
        outer.addWidget(make_scroll_page(content))

    def load_laureate(self, laureate_id: int):
        self._laureate_id = laureate_id
        try:
            data = self.api.get_laureate(laureate_id)
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить лауреата:\n{e.detail}")
            return
        self._populate_fields(data)
        self._load_awards()
        self._load_monitor()
        self._dirty = False

    def _load_monitor(self):
        if self._laureate_id is None:
            return
        try:
            rows = self.api.get_laureate_awards_monitor(self._laureate_id)
        except APIError:
            rows = []
        self.monitor_table.setRowCount(len(rows))
        flags = (
            "nomination_done", "voting_done", "decision_done",
            "registration_done", "ceremony_done", "publication_done",
        )
        for i, row in enumerate(rows):
            self.monitor_table.setItem(i, 0, self._make_item(row.get("award_name", "")))
            for j, key in enumerate(flags, start=1):
                done = row.get(key)
                item = QTableWidgetItem("✓" if done else "✗")
                item.setTextAlignment(Qt.AlignCenter)
                if done:
                    item.setBackground(QBrush(QColor("#E8F5E9")))
                else:
                    item.setBackground(QBrush(QColor("#FFEBEE")))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.monitor_table.setItem(i, j, item)

    def _populate_fields(self, data: dict):
        self._original_data = dict(data)
        self.title_label.setText(f"Карточка: {data.get('full_name', '')}")
        self.full_name.setText(data.get("full_name", ""))

        cat = data.get("category", "")
        idx = self.category.findData(cat or "")
        self.category.setCurrentIndex(max(idx, 0))

        self.position.setText(data.get("position", "") or "")
        self.organization.setText(data.get("organization", "") or "")
        self.phone.setText(data.get("phone", "") or "")
        self.email.setText(data.get("email", "") or "")
        self.address.setText(data.get("address", "") or "")
        self.birth_date.setText(str(data.get("birth_date") or ""))
        self.passport.setText(data.get("passport", "") or "")
        self.inn.setText(data.get("inn", "") or "")
        self.snils.setText(data.get("snils", "") or "")
        self.regalia.setPlainText(data.get("regalia", "") or "")
        self.notes.setPlainText(data.get("notes", "") or "")
        self._load_laureate_photo(bool(data.get("has_photo")))

    def _load_laureate_photo(self, has_photo: bool):
        if not has_photo or self._laureate_id is None:
            set_photo_placeholder(self.photo_label, "нет фото")
            return
        try:
            raw = self.api.download_laureate_photo(self._laureate_id)
            set_photo_bytes(self.photo_label, raw)
        except APIError:
            set_photo_placeholder(self.photo_label, "есть фото")

    def _load_awards(self):
        if self._laureate_id is None:
            return
        try:
            awards = self.api.get_laureate_awards(self._laureate_id)
        except APIError:
            awards = []

        self.awards_table.setSortingEnabled(False)
        self.awards_table.setRowCount(len(awards))
        for row, la in enumerate(awards):
            la_id = la.get("id", "")
            self.awards_table.setItem(row, 0, NumericSortTableItem(str(la_id), la_id))
            self.awards_table.setItem(
                row, 1, NumericSortTableItem(str(la.get("award_id", "")), la.get("award_id")),
            )
            self.awards_table.setItem(row, 2, self._make_item(str(la.get("assigned_date", "") or "")))
            self.awards_table.setItem(row, 3, self._make_item(la.get("status", "")))

            progress = self._get_lifecycle_progress(la_id)
            pbar = QProgressBar()
            pbar.setMinimumHeight(28)
            pbar.setRange(0, 6)
            pbar.setValue(progress)
            pbar.setFormat(f"{progress}/6 этапов")
            pbar.setTextVisible(True)
            if progress == 6:
                pbar.setStyleSheet("QProgressBar::chunk { background: #4CAF50; }")
            elif progress > 0:
                pbar.setStyleSheet("QProgressBar::chunk { background: #FFC107; }")
            else:
                pbar.setStyleSheet("QProgressBar::chunk { background: #E0E0E0; }")
            self.awards_table.setCellWidget(row, 4, pbar)
            self.awards_table.setRowHeight(row, 40)
        self.awards_table.setSortingEnabled(True)
        self._load_extracts(awards)

    def _load_extracts(self, awards: list):
        rows: list[tuple] = []
        for la in awards:
            la_id = la.get("id")
            if la_id is None:
                continue
            try:
                ctx = self.api.get_laureate_award_context(int(la_id))
            except APIError:
                continue
            for ex in ctx.get("extracts") or []:
                extract_id = ex.get("id")
                rows.append((
                    str(la_id),
                    str(ex.get("extract_date") or ""),
                    (ex.get("details") or "")[:80],
                    str(extract_id or ""),
                    extract_id,
                ))
        self.extracts_table.setRowCount(len(rows))
        for i, cells in enumerate(rows):
            for j in range(4):
                item = self._make_item(cells[j])
                if j == 3 and cells[4] is not None:
                    item.setData(Qt.UserRole, int(cells[4]))
                self.extracts_table.setItem(i, j, item)

    def _get_lifecycle_progress(self, laureate_award_id: int) -> int:
        try:
            lc = self.api.get_laureate_lifecycle(laureate_award_id)
        except APIError:
            return 0
        return sum(1 for stage in LIFECYCLE_STAGES if lc.get(stage))

    @staticmethod
    def _make_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _mark_dirty(self):
        self._dirty = True
        if connection_state.is_online:
            self._autosave_timer.start(1500)

    def _autosave_silent(self):
        self._on_save(silent=True)

    def _collect_data(self) -> dict:
        data: dict = {"full_name": self.full_name.text().strip()}
        cat = self.category.currentData()
        if cat:
            data["category"] = cat
        else:
            data["category"] = None
        for field in ("position", "organization", "phone", "email", "address",
                      "birth_date", "passport", "inn", "snils"):
            data[field] = getattr(self, field).text().strip() or None
        data["regalia"] = self.regalia.toPlainText().strip() or None
        data["notes"] = self.notes.toPlainText().strip() or None
        return data

    def _on_upload_photo(self):
        if self._laureate_id is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Фото лауреата", "", "Изображения (*.png *.jpg *.jpeg);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            self.api.upload_laureate_photo(self._laureate_id, path)
            self._load_laureate_photo(True)
            QMessageBox.information(self, "Фото", "Фотография загружена.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", str(e.detail))

    def _on_save(self, silent: bool = False):
        if self._laureate_id is None:
            return
        if silent and not connection_state.is_online:
            return
        if not silent and not warn_if_offline(self, "Сохранение"):
            return
        data = self._collect_data()
        if not data.get("full_name"):
            if not silent:
                QMessageBox.warning(self, "Ошибка", "Поле «ФИО» обязательно.")
            return
        label = data["full_name"]
        try:
            updated = self.api.update_laureate(self._laureate_id, data)
            self._populate_fields(updated)
            self._dirty = False
            if not silent:
                QMessageBox.information(self, "Сохранено", "Данные лауреата обновлены.")
        except APIError as e:
            if save_local_draft_on_failure(
                kind="laureate",
                entity_id=self._laureate_id,
                label=label,
                payload=data,
                parent=self,
                silent=silent,
                error=e,
            ):
                return
            if not silent:
                QMessageBox.critical(self, "Ошибка", user_facing_error(e))

    def _on_delete(self):
        if self._laureate_id is None:
            return
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить лауреата «{self.full_name.text()}»?\nЭто действие необратимо.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.api.delete_laureate(self._laureate_id)
                QMessageBox.information(self, "Удалено", "Лауреат удалён.")
                self.back_requested.emit()
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{e.detail}")

    def _on_back(self):
        if not self.confirm_quit_application():
            return
        self.back_requested.emit()

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

    def _selected_extract_id(self) -> int | None:
        rows = self.extracts_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.extracts_table.item(rows[0].row(), 3)
        if item is None:
            return None
        extract_id = item.data(Qt.UserRole)
        if extract_id is None:
            try:
                extract_id = int(item.text())
            except (TypeError, ValueError):
                return None
        return int(extract_id)

    def _on_extract_double_click(self, index):
        if index.column() == 3 or index.column() == 0:
            self._on_download_extract()

    def _on_download_extract(self):
        extract_id = self._selected_extract_id()
        if extract_id is None:
            rows = self.extracts_table.selectionModel().selectedRows()
            if not rows:
                QMessageBox.information(self, "Выписка", "Выберите выписку в таблице.")
                return
            QMessageBox.warning(self, "Выписка", "Не удалось определить ID выписки.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить выписку (DOCX)",
            f"выписка_{extract_id}.docx",
            "Документ Word (*.docx);;Все файлы (*.*)",
        )
        if not path:
            return
        try:
            data = self.api.download_extract_docx(extract_id)
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Word (DOCX)", "Файл сохранён.")
        except APIError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось скачать DOCX:\n{e.detail}")

    def _on_award_double_click(self, index):
        row = index.row()
        la_id_item = self.awards_table.item(row, 0)
        if la_id_item:
            self.open_lifecycle.emit(int(la_id_item.text()))
