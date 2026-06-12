"""Экран «Склад на награду» (ТЗ file-012)."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QGroupBox, QFormLayout, QSpinBox,
    QComboBox, QMessageBox, QAbstractItemView,
)
from PyQt5.QtCore import Qt

from api_client import APIClient, APIError
from ui.awards.warehouse import KIT_TYPE_OPTIONS, _EditInventoryDialog
from ui.table_fill import configure_table_rows

_INV_COLUMNS = ["Компонент", "Всего", "Резерв", "Выдано", "Доступно"]


class AwardWarehouseDialog(QDialog):
    """Склад одной награды: остатки, сборка комплектов, выбытие."""

    def __init__(
        self,
        api: APIClient,
        award_id: int,
        award_name: str,
        parent=None,
    ):
        super().__init__(parent)
        self.api = api
        self.award_id = award_id
        self.award_name = award_name
        self._inventory: list[dict] = []

        self.setWindowTitle(f"Склад — {award_name}")
        self.setMinimumSize(720, 520)
        root = QVBoxLayout(self)

        self.status_label = QLabel("Загрузка…")
        root.addWidget(self.status_label)

        inv_group = QGroupBox("Компоненты на складе")
        ig = QVBoxLayout(inv_group)
        self.inv_table = QTableWidget()
        self.inv_table.setColumnCount(len(_INV_COLUMNS))
        self.inv_table.setHorizontalHeaderLabels(_INV_COLUMNS)
        self.inv_table.horizontalHeader().setStretchLastSection(True)
        self.inv_table.verticalHeader().setVisible(False)
        self.inv_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inv_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        configure_table_rows(self.inv_table, 34)
        self.inv_table.doubleClicked.connect(self._on_edit_inventory)
        ig.addWidget(self.inv_table)
        btn_inv = QHBoxLayout()
        btn_inv.addStretch()
        btn_edit = QPushButton("Изменить остатки…")
        btn_edit.clicked.connect(self._on_edit_inventory)
        btn_inv.addWidget(btn_edit)
        ig.addLayout(btn_inv)
        root.addWidget(inv_group, 1)

        kits_group = QGroupBox("Комплекты")
        kg = QFormLayout(kits_group)
        self.kit_type_combo = QComboBox()
        for val, label in KIT_TYPE_OPTIONS:
            self.kit_type_combo.addItem(label, val or None)
        kg.addRow("Тип комплекта:", self.kit_type_combo)
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 9999)
        self.qty_spin.setValue(1)
        kg.addRow("Количество:", self.qty_spin)
        kit_btns = QHBoxLayout()
        btn_asm = QPushButton("Собрать")
        btn_asm.clicked.connect(self._on_assemble)
        kit_btns.addWidget(btn_asm)
        btn_dis = QPushButton("Разобрать")
        btn_dis.setProperty("class", "btn-secondary")
        btn_dis.clicked.connect(self._on_disassemble)
        kit_btns.addWidget(btn_dis)
        btn_la = QPushButton("Выбытие лауреату…")
        btn_la.clicked.connect(self._on_disposal_laureate)
        kit_btns.addWidget(btn_la)
        btn_other = QPushButton("Выбытие (иное)…")
        btn_other.setProperty("class", "btn-secondary")
        btn_other.clicked.connect(self._on_disposal_other)
        kit_btns.addWidget(btn_other)
        kg.addRow(kit_btns)
        root.addWidget(kits_group)

        disp_group = QGroupBox("Журнал выбытия (эта награда)")
        dg = QVBoxLayout(disp_group)
        self.disp_table = QTableWidget()
        self.disp_table.setColumnCount(5)
        self.disp_table.setHorizontalHeaderLabels(
            ["ID", "Назначение", "Кол-во", "Событие", "Дата"],
        )
        self.disp_table.horizontalHeader().setStretchLastSection(True)
        self.disp_table.verticalHeader().setVisible(False)
        configure_table_rows(self.disp_table, 30)
        dg.addWidget(self.disp_table)
        root.addWidget(disp_group)

        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        root.addWidget(close)

        from ui.help_installer import install_help_for_page
        install_help_for_page(self, "award_warehouse_dialog")

        self._refresh()

    def _kit_type(self) -> str | None:
        return self.kit_type_combo.currentData()

    def _refresh(self):
        try:
            st = self.api.get_kit_status(self.award_id)
            inv = self.api.get_inventory(self.award_id)
            disposals = self.api.list_kit_disposals(self.award_id)
        except APIError as e:
            self.status_label.setText(f"Ошибка: {e.detail}")
            return

        self._inventory = inv
        self.status_label.setText(
            f"Физически: {st.get('physical_sets', 0)}  |  "
            f"Свободно: {st.get('free_sets', 0)}  |  "
            f"Отложено: {st.get('postponed_sets', 0)}  |  "
            f"Можно собрать из комплектующих: {st.get('can_assemble_from_loose', 0)}"
        )

        self.inv_table.setRowCount(len(inv))
        for row, item in enumerate(inv):
            self.inv_table.setItem(row, 0, QTableWidgetItem(str(item.get("component_type", ""))))
            self.inv_table.setItem(row, 1, QTableWidgetItem(str(item.get("total_count", 0))))
            self.inv_table.setItem(row, 2, QTableWidgetItem(str(item.get("reserve_count", 0))))
            self.inv_table.setItem(row, 3, QTableWidgetItem(str(item.get("issued_count", 0))))
            self.inv_table.setItem(row, 4, QTableWidgetItem(str(item.get("available_count", 0))))
            id_item = self.inv_table.item(row, 0)
            if id_item:
                id_item.setData(Qt.UserRole, item.get("id"))

        self.disp_table.setRowCount(len(disposals))
        for row, d in enumerate(disposals):
            tgt = d.get("target", "")
            if tgt == "laureate":
                tgt_ru = f"лауреат (#{d.get('laureate_award_id')})"
            else:
                tgt_ru = "иное"
            self.disp_table.setItem(row, 0, QTableWidgetItem(str(d.get("id", ""))))
            self.disp_table.setItem(row, 1, QTableWidgetItem(tgt_ru))
            self.disp_table.setItem(row, 2, QTableWidgetItem(str(d.get("quantity", 1))))
            self.disp_table.setItem(row, 3, QTableWidgetItem(d.get("event_name") or d.get("reason") or ""))
            self.disp_table.setItem(row, 4, QTableWidgetItem(str(d.get("disposal_date") or "")))

    def _on_edit_inventory(self):
        row = self.inv_table.currentRow()
        if row < 0 or row >= len(self._inventory):
            return
        item = dict(self._inventory[row])
        item["award_name"] = self.award_name
        item["component_type"] = str(item.get("component_type", ""))
        dlg = _EditInventoryDialog(item, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        data = dlg.get_data()
        data["available_count"] = (
            data["total_count"] - data["reserve_count"] - data["issued_count"]
        )
        try:
            self.api.update_inventory_item(int(item["id"]), data)
            self._refresh()
        except APIError as e:
            QMessageBox.warning(self, "Склад", str(e.detail))

    def _on_assemble(self):
        try:
            self.api.assemble_kits(
                self.award_id, self.qty_spin.value(), kit_type=self._kit_type(),
            )
            self._refresh()
            QMessageBox.information(self, "Склад", "Комплекты собраны.")
        except APIError as e:
            QMessageBox.warning(self, "Сборка", str(e.detail))

    def _on_disassemble(self):
        try:
            self.api.disassemble_kits(
                self.award_id, self.qty_spin.value(), kit_type=self._kit_type(),
            )
            self._refresh()
            QMessageBox.information(self, "Склад", "Комплекты разобраны.")
        except APIError as e:
            QMessageBox.warning(self, "Разборка", str(e.detail))

    def _on_disposal_laureate(self):
        from ui.awards.warehouse import _KitLaureateDisposalDialog

        awards = [{"id": self.award_id, "name": self.award_name}]
        dlg = _KitLaureateDisposalDialog(self.api, awards, self)
        dlg.award_combo.setCurrentIndex(0)
        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            award_id, body = dlg.get_data()
            self.api.create_kit_disposal(award_id, body)
            self._refresh()
        except (ValueError, APIError) as e:
            QMessageBox.warning(self, "Выбытие", str(e))

    def _on_disposal_other(self):
        from PyQt5.QtWidgets import QLineEdit, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle("Выбытие — иное")
        form = QFormLayout(dlg)
        qty = QSpinBox()
        qty.setRange(1, 9999)
        qty.setValue(1)
        form.addRow("Количество:", qty)
        reason = QLineEdit()
        form.addRow("Причина:", reason)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            self.api.create_kit_disposal(self.award_id, {
                "target": "other",
                "quantity": qty.value(),
                "reason": reason.text().strip() or None,
            })
            self._refresh()
        except APIError as e:
            QMessageBox.warning(self, "Выбытие", str(e.detail))
