"""Диалог «Производство — компонент» (ТЗ file-008)."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QComboBox, QCheckBox,
    QLabel, QMessageBox, QFileDialog, QAbstractItemView,
)
from PyQt5.QtCore import Qt

from api_client import APIClient, APIError
from ui.table_fill import configure_table_rows

PRODUCTION_STAGE_STATUSES = [
    "",
    "Не начато",
    "В работе",
    "Ожидание",
    "Завершено",
    "Отменено",
]

_COMPONENT_RU = {
    "medal": "Медаль",
    "badge": "Значок",
    "cufflinks": "Запонки",
    "pendant": "Кулон",
    "ppz": "ППЗ",
}


class ProductionComponentDialog(QDialog):
    """10 этапов одного компонента: combobox статусов, файлы вложений."""

    STAGE_COLUMNS = ["Этап", "Статус", "Дата", "Примечание", "Файлы"]

    def __init__(
        self,
        api: APIClient,
        award_id: int,
        component_type: str,
        component_data: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.api = api
        self.award_id = award_id
        self.component_type = component_type
        ru = _COMPONENT_RU.get(component_type, component_type)
        self.setWindowTitle(f"Производство — {ru}")
        self.setMinimumSize(820, 520)
        self._attachment_counts: dict[str, int] = {}

        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel(f"Компонент: {ru}"))
        header.addStretch()
        self.ready_check = QCheckBox("Компонент готов")
        header.addWidget(self.ready_check)
        root.addLayout(header)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.STAGE_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.STAGE_COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        configure_table_rows(self.table, 38)
        root.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)
        btn_close = QPushButton("Закрыть")
        btn_close.setProperty("class", "btn-secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

        if component_data:
            self.set_component_data(component_data)
        else:
            self._load_from_api()

    def _load_from_api(self):
        try:
            data = self.api.get_production_stages(self.award_id)
        except APIError as e:
            QMessageBox.warning(self, "Производство", str(e.detail))
            return
        comp = next(
            (c for c in (data.get("components") or []) if c.get("component_type") == self.component_type),
            None,
        )
        if comp:
            self.set_component_data(comp)

    def set_component_data(self, comp: dict):
        stages = comp.get("stages") or []
        self.ready_check.setChecked(bool(comp.get("is_ready")))
        self.table.setRowCount(len(stages))
        for row, st in enumerate(stages):
            key = st.get("stage_key", "")
            self._attachment_counts[key] = int(st.get("attachment_count") or 0)

            label_item = QTableWidgetItem(st.get("label") or key)
            label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
            label_item.setData(Qt.UserRole, key)
            self.table.setItem(row, 0, label_item)

            status_combo = QComboBox()
            status_combo.setEditable(True)
            cur = st.get("status") or ""
            for s in PRODUCTION_STAGE_STATUSES:
                status_combo.addItem(s)
            if cur and cur not in PRODUCTION_STAGE_STATUSES:
                status_combo.addItem(cur)
            idx = status_combo.findText(cur)
            status_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.table.setCellWidget(row, 1, status_combo)

            self.table.setItem(row, 2, QTableWidgetItem(str(st.get("stage_date") or "")))
            self.table.setItem(row, 3, QTableWidgetItem(st.get("attachment_note") or ""))

            files_btn = QPushButton(self._files_label(key))
            files_btn.clicked.connect(lambda _checked=False, r=row: self._on_files(r))
            self.table.setCellWidget(row, 4, files_btn)

    def _files_label(self, stage_key: str) -> str:
        n = self._attachment_counts.get(stage_key, 0)
        return f"Файлы ({n})" if n else "Файлы…"

    def _stage_key_at(self, row: int) -> str | None:
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _refresh_files_button(self, row: int, stage_key: str):
        btn = self.table.cellWidget(row, 4)
        if isinstance(btn, QPushButton):
            btn.setText(self._files_label(stage_key))

    def _on_files(self, row: int):
        stage_key = self._stage_key_at(row)
        if not stage_key:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Вложение этапа", "", "Все файлы (*.*)",
        )
        if not path:
            return
        try:
            self.api.upload_production_stage_attachment(
                self.award_id, self.component_type, stage_key, path,
            )
            self._attachment_counts[stage_key] = self._attachment_counts.get(stage_key, 0) + 1
            self._refresh_files_button(row, stage_key)
            QMessageBox.information(self, "Вложение", "Файл загружен.")
        except APIError as e:
            QMessageBox.critical(self, "Вложение", str(e.detail))

    def _collect_stages(self) -> list[dict]:
        stages = []
        for row in range(self.table.rowCount()):
            key = self._stage_key_at(row)
            if not key:
                continue
            combo = self.table.cellWidget(row, 1)
            status = combo.currentText() if isinstance(combo, QComboBox) else ""
            date_item = self.table.item(row, 2)
            note_item = self.table.item(row, 3)
            stages.append({
                "stage_key": key,
                "status": status,
                "stage_date": date_item.text() if date_item else "",
                "attachment_note": note_item.text() if note_item else "",
            })
        return stages

    def _on_save(self):
        try:
            updated = self.api.update_production_stages(self.award_id, {
                "component_type": self.component_type,
                "is_ready": self.ready_check.isChecked(),
                "stages": self._collect_stages(),
            })
        except APIError as e:
            QMessageBox.critical(self, "Производство", str(e.detail))
            return
        for st in updated.get("stages") or []:
            key = st.get("stage_key")
            if key:
                self._attachment_counts[key] = int(st.get("attachment_count") or 0)
        for row in range(self.table.rowCount()):
            key = self._stage_key_at(row)
            if key:
                self._refresh_files_button(row, key)
        QMessageBox.information(self, "Производство", "Сохранено.")
