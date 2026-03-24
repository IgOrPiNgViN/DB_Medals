from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QProgressBar,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt5.QtCore import Qt


KNOWN_TABLES = [
    "awards", "award_characteristics", "award_establishments",
    "award_developments", "award_approvals", "award_productions",
    "inventory_items", "laureates", "laureate_awards",
    "laureate_lifecycles", "committee_members", "member_signing_rights",
    "bulletins", "bulletin_sections", "bulletin_questions",
    "bulletin_distributions", "votes", "protocols",
    "protocol_extracts", "ppz_submissions",
]


class DBExportPage(QWidget):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Выгрузка базы данных")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        # Full backup section
        backup_group = QGroupBox("Полный бэкап PostgreSQL (pg_dump)")
        bg_layout = QVBoxLayout(backup_group)

        desc = QLabel(
            "Создаёт полный дамп базы данных PostgreSQL.\n"
            "Файл можно использовать для восстановления в случае сбоя сервера."
        )
        desc.setWordWrap(True)
        bg_layout.addWidget(desc)

        btn_row = QHBoxLayout()
        self.btn_export_dump = QPushButton("Скачать дамп БД")
        self.btn_export_dump.setProperty("class", "primary")
        self.btn_export_dump.clicked.connect(self._export_dump)
        btn_row.addWidget(self.btn_export_dump)

        self.btn_import_dump = QPushButton("Восстановить из дампа")
        self.btn_import_dump.setProperty("class", "secondary")
        self.btn_import_dump.clicked.connect(self._import_dump)
        btn_row.addWidget(self.btn_import_dump)
        btn_row.addStretch()
        bg_layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        bg_layout.addWidget(self.progress)

        layout.addWidget(backup_group)

        # CSV export section
        csv_group = QGroupBox("Экспорт отдельных таблиц в CSV")
        cg_layout = QVBoxLayout(csv_group)

        csv_desc = QLabel(
            "Выберите таблицу и скачайте её содержимое в формате CSV."
        )
        csv_desc.setWordWrap(True)
        cg_layout.addWidget(csv_desc)

        csv_row = QHBoxLayout()
        csv_row.addWidget(QLabel("Таблица:"))
        self.table_combo = QComboBox()
        self.table_combo.addItems(KNOWN_TABLES)
        csv_row.addWidget(self.table_combo)

        self.btn_export_csv = QPushButton("Скачать CSV")
        self.btn_export_csv.setProperty("class", "primary")
        self.btn_export_csv.clicked.connect(self._export_csv)
        csv_row.addWidget(self.btn_export_csv)
        csv_row.addStretch()
        cg_layout.addLayout(csv_row)

        layout.addWidget(csv_group)
        layout.addStretch()

    def _export_dump(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить дамп БД", "awards_backup.sql",
            "SQL Files (*.sql);;All Files (*)",
        )
        if not path:
            return
        try:
            self.progress.setVisible(True)
            self.progress.setRange(0, 0)
            data = self.api.export_backup()
            with open(path, "wb") as f:
                f.write(data)
            self.progress.setVisible(False)
            QMessageBox.information(self, "Успех", f"Дамп сохранён:\n{path}")
        except Exception as e:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Ошибка", f"Не удалось выгрузить БД:\n{e}")

    def _import_dump(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать файл дампа", "",
            "SQL Files (*.sql);;All Files (*)",
        )
        if not path:
            return
        confirm = QMessageBox.warning(
            self, "Подтверждение",
            "Восстановление из дампа перезапишет текущие данные!\n\nПродолжить?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.progress.setVisible(True)
            self.progress.setRange(0, 0)
            with open(path, "rb") as f:
                self.api.import_backup(f)
            self.progress.setVisible(False)
            QMessageBox.information(self, "Успех", "База данных восстановлена из дампа.")
        except Exception as e:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "Ошибка", f"Не удалось восстановить БД:\n{e}")

    def _export_csv(self):
        table_name = self.table_combo.currentText()
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить CSV", f"{table_name}.csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return
        try:
            data = self.api.export_table_csv(table_name)
            with open(path, "wb") as f:
                f.write(data)
            QMessageBox.information(self, "Успех", f"Таблица '{table_name}' сохранена:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось выгрузить таблицу:\n{e}")
