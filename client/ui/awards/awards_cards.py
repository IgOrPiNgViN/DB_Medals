import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QAbstractItemView, QScrollArea, QFrame,
    QGridLayout, QStackedWidget, QSizePolicy, QFileDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QFont, QImage, QPixmap

from api_client import APIClient, APIError
from ui.numeric_sort_item import NumericSortTableItem

AWARD_TYPE_FILTER = [
    ("Все", None),
    ("Медали", "Медали"),
    ("ППЗ", "ППЗ"),
    ("Знаки отличия", "Знаки отличия"),
    ("Украшения", "Украшения"),
]

# Значения для API (enum)
_AWARD_TYPE_API = {
    "Медали": "medal",
    "ППЗ": "ppz",
    "Знаки отличия": "distinction",
    "Украшения": "decoration",
}


class CreateAwardDialog(QDialog):
    """Modal dialog for creating a new award."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новая награда")
        self.setMinimumWidth(420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите название награды")
        form.addRow("Название:", self.name_edit)

        self.type_combo = QComboBox()
        for label, value in AWARD_TYPE_FILTER[1:]:
            self.type_combo.addItem(label, value)
        form.addRow("Тип:", self.type_combo)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Краткое описание (необязательно)")
        form.addRow("Описание:", self.description_edit)

        self._path_front: str = ""
        self._path_back: str = ""
        self.lbl_img_front = QLabel("Лицо: не выбрано")
        self.lbl_img_back = QLabel("Оборот: не выбрано")
        self.lbl_img_front.setWordWrap(True)
        self.lbl_img_back.setWordWrap(True)
        row_img_f = QHBoxLayout()
        row_img_f.addWidget(self.lbl_img_front, 1)
        btn_f = QPushButton("Лицо…")
        btn_f.clicked.connect(lambda: self._browse_image("front"))
        row_img_f.addWidget(btn_f)
        row_img_b = QHBoxLayout()
        row_img_b.addWidget(self.lbl_img_back, 1)
        btn_b = QPushButton("Оборот…")
        btn_b.clicked.connect(lambda: self._browse_image("back"))
        row_img_b.addWidget(btn_b)
        img_block = QVBoxLayout()
        img_block.addLayout(row_img_f)
        img_block.addLayout(row_img_b)
        form.addRow("Изображения:", img_block)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setProperty("class", "btn-secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("Создать")
        ok_btn.setProperty("class", "btn-success")
        ok_btn.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    def _validate_and_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите название награды.")
            return
        self.accept()

    def _browse_image(self, side: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите изображение",
            "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;Все файлы (*.*)",
        )
        if not path:
            return
        base = os.path.basename(path)
        if side == "front":
            self._path_front = path
            self.lbl_img_front.setText(f"Лицо: {base}")
        else:
            self._path_back = path
            self.lbl_img_back.setText(f"Оборот: {base}")

    def get_image_paths(self) -> tuple[str | None, str | None]:
        return (
            self._path_front or None,
            self._path_back or None,
        )

    def get_data(self) -> dict:
        ru = self.type_combo.currentData()
        data = {
            "name": self.name_edit.text().strip(),
            "award_type": _AWARD_TYPE_API.get(ru, "medal"),
        }
        desc = self.description_edit.text().strip()
        if desc:
            data["description"] = desc
        return data


class _AwardCatalogCard(QFrame):
    """Карточка награды: эскиз + подпись (как каталог в Access)."""

    clicked_id = pyqtSignal(int)

    def __init__(
        self,
        award_id: int,
        name: str,
        api: APIClient,
        has_image: bool = False,
        has_image_back: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._award_id = award_id
        self._api = api
        self._has_image = has_image
        self._has_image_back = has_image_back
        self.setObjectName("AwardCatalogCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.setFixedWidth(196)
        self.setStyleSheet(
            """
            QFrame#AwardCatalogCard {
                background: #ffffff;
                border: 1px solid #c5cdd8;
                border-radius: 10px;
            }
            QFrame#AwardCatalogCard:hover {
                border-color: #2196F3;
            }
            """
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setSpacing(10)

        self._img = QLabel()
        self._img.setFixedSize(160, 160)
        self._img.setAlignment(Qt.AlignCenter)
        self._img.setStyleSheet("background: #f4f6f9; border-radius: 8px;")
        lay.addWidget(self._img, 0, Qt.AlignHCenter)

        title = QLabel(name)
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignCenter)
        tf = QFont()
        tf.setPointSize(9)
        title.setFont(tf)
        title.setStyleSheet("color: #1a2332;")
        lay.addWidget(title)

        # Загружаем эскиз асинхронно — карточка сразу отображается,
        # изображение подгружается после первой отрисовки UI.
        QTimer.singleShot(0, self._load_thumb)

    def _load_thumb(self) -> None:
        pm = QPixmap(160, 160)
        pm.fill(Qt.transparent)
        if not self._has_image and not self._has_image_back:
            self._img.setPixmap(pm)
            return
        try:
            data = None
            if self._has_image:
                data = self._api.get_award_image_bytes(self._award_id, "front")
            if not data and self._has_image_back:
                data = self._api.get_award_image_bytes(self._award_id, "back")
            if data:
                p = QPixmap()
                if p.loadFromData(data):
                    pm = p.scaled(
                        160, 160,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                else:
                    img = QImage.fromData(data)
                    if not img.isNull():
                        pm = QPixmap.fromImage(img).scaled(
                            160, 160,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        )
        except Exception:
            pass  # сетевая ошибка — показываем пустой placeholder
        self._img.setPixmap(pm)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked_id.emit(self._award_id)
        super().mouseReleaseEvent(event)


class AwardsCardsPage(QWidget):
    """Каталог наград (сетка с картинками) и табличный вид."""

    award_selected = pyqtSignal(int)

    COLUMNS = ["№", "Название", "Тип", "Дата создания"]
    GRID_COLS = 5

    def __init__(self, api_client: APIClient, parent=None):
        super().__init__(parent)
        self.api = api_client
        self._catalog_inner: QWidget | None = None
        self._catalog_grid: QGridLayout | None = None
        self._catalog_scroll: QScrollArea | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(12)

        title = QLabel("Карточки наград")
        title.setProperty("class", "page-title")
        title.setStyleSheet("padding: 0;")
        root.addWidget(title)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        toolbar.addWidget(QLabel("Тип награды:"))
        self.filter_combo = QComboBox()
        self.filter_combo.setMinimumWidth(180)
        for label, _ in AWARD_TYPE_FILTER:
            self.filter_combo.addItem(label)
        toolbar.addWidget(self.filter_combo)

        self.view_combo = QComboBox()
        self.view_combo.addItem("Каталог (как в Access)", "catalog")
        self.view_combo.addItem("Таблица", "table")
        toolbar.addWidget(self.view_combo)

        toolbar.addStretch()

        self.btn_add = QPushButton("Новая награда")
        self.btn_add.setProperty("class", "btn-success")
        self.btn_add.clicked.connect(self._on_create)
        toolbar.addWidget(self.btn_add)

        self.btn_delete = QPushButton("Удалить награду")
        self.btn_delete.setProperty("class", "btn-danger")
        self.btn_delete.clicked.connect(self._on_delete)
        toolbar.addWidget(self.btn_delete)

        root.addLayout(toolbar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background: #e4eaf2; border-radius: 8px; }")

        catalog_scroll = QScrollArea()
        self._catalog_scroll = catalog_scroll
        catalog_scroll.setWidgetResizable(True)
        catalog_scroll.setFrameShape(QScrollArea.NoFrame)
        catalog_scroll.setStyleSheet("QScrollArea { background: transparent; }")
        catalog_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._catalog_inner = QWidget()
        self._catalog_inner.setStyleSheet("background: transparent;")
        self._catalog_inner.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self._catalog_grid = QGridLayout(self._catalog_inner)
        self._catalog_grid.setSpacing(18)
        self._catalog_grid.setContentsMargins(20, 20, 20, 20)
        catalog_scroll.setWidget(self._catalog_inner)
        self.stack.addWidget(catalog_scroll)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setSortingEnabled(True)
        self.stack.addWidget(self.table)

        root.addWidget(self.stack, 1)

        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.view_combo.currentIndexChanged.connect(self._on_view_changed)
        self._sync_stack_to_view()
        # Первичная отрисовка каталога после того, как у страницы есть геометрия (иначе сетка в QScrollArea бывает пустой).
        QTimer.singleShot(0, self.refresh)

    # ── data loading ─────────────────────────────────────────────────

    def refresh(self):
        _, type_value = AWARD_TYPE_FILTER[self.filter_combo.currentIndex()]
        print(f"[refresh] запрос наград, фильтр={type_value!r}", flush=True)
        try:
            awards = self.api.get_awards(award_type=type_value)
        except APIError as e:
            print(f"[refresh] ОШИБКА API: {e}")
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось загрузить награды.\n{e}")
            return

        # Стабильная сортировка для каталога/таблицы (по названию, затем по ID)
        awards = sorted(
            awards or [],
            key=lambda a: (
                str(a.get("name") or "").strip().lower(),
                int(a.get("id") or 0),
            ),
        )

        print(f"[refresh] получено {len(awards)} наград")
        self._rebuild_catalog(awards)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(awards))
        for row, award in enumerate(awards):
            self.table.setItem(row, 0, self._numeric_id_item(str(award.get("id", ""))))
            self.table.setItem(row, 1, self._item(award.get("name", "")))
            at = str(award.get("award_type", "") or "")
            at_ru = {
                "medal": "Медали",
                "ppz": "ППЗ",
                "distinction": "Знаки отличия",
                "decoration": "Украшения",
            }.get(at, at)
            self.table.setItem(row, 2, self._item(at_ru))
            self.table.setItem(row, 3, self._item(str(award.get("created_at", ""))))
        self.table.setSortingEnabled(True)

    def _rebuild_catalog(self, awards: list) -> None:
        print(f"[rebuild] вызван, наград={len(awards)}, grid={self._catalog_grid is not None}", flush=True)
        # В PyQt5 bool(QGridLayout)==False пока в сетке 0 элементов — нельзя писать «if not layout».
        if self._catalog_grid is None:
            print("[rebuild] grid=None — выход", flush=True)
            return
        # Удаляем старые карточки
        old_n = self._catalog_grid.count()
        while self._catalog_grid.count():
            item = self._catalog_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        print(f"[rebuild] очищено {old_n} старых карточек", flush=True)

        cols = self.GRID_COLS
        if not awards:
            print("[rebuild] список пуст — каталог не заполняется", flush=True)
            hint = QLabel(
                "Награды не найдены (пустой ответ от сервера или слишком строгий фильтр).\n"
                "Проверьте импорт БД и что API отдаёт список: GET /api/awards/",
            )
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignCenter)
            hint.setStyleSheet("color: #334155; font-size: 14px; padding: 40px 24px;")
            self._catalog_grid.addWidget(hint, 0, 0, 1, cols)
            if self._catalog_scroll is not None:
                self._catalog_scroll.updateGeometry()
            return
        print(f"[rebuild] создаём {len(awards)} карточек по {cols} в ряд", flush=True)
        created = 0
        for i, award in enumerate(awards):
            aid = int(award.get("id", 0))
            name = str(award.get("name", ""))
            has_img = bool(award.get("has_image"))
            has_img_back = bool(award.get("has_image_back"))
            try:
                card = _AwardCatalogCard(
                    aid, name, self.api,
                    has_image=has_img,
                    has_image_back=has_img_back,
                    parent=self._catalog_inner,
                )
                card.clicked_id.connect(self.award_selected.emit)
                r, c = divmod(i, cols)
                self._catalog_grid.addWidget(card, r, c)
                card.show()
                created += 1
            except Exception as _card_err:
                import traceback
                print(f"[CARD ERROR] id={aid}: {_card_err}", flush=True)
                traceback.print_exc()

        nrows = (len(awards) + cols - 1) // cols
        print(f"[rebuild] создано={created}, итого в сетке: {self._catalog_grid.count()} виджетов, {nrows} рядов", flush=True)
        # Принудительно пересчитаем геометрию контейнера
        if self._catalog_inner is not None:
            self._catalog_inner.adjustSize()
            self._catalog_inner.updateGeometry()
            print(f"[rebuild] inner.size={self._catalog_inner.size().width()}x{self._catalog_inner.size().height()}, "
                  f"sizeHint={self._catalog_inner.sizeHint().width()}x{self._catalog_inner.sizeHint().height()}", flush=True)
        if self._catalog_scroll is not None:
            self._catalog_scroll.updateGeometry()

    def showEvent(self, event):
        print("[showEvent] AwardsCardsPage показана")
        super().showEvent(event)
        QTimer.singleShot(0, self.refresh)

    def _sync_stack_to_view(self):
        mode = self.view_combo.currentData()
        if mode is None:
            mode = "catalog"
        idx = 0 if mode == "catalog" else 1
        if 0 <= idx < self.stack.count():
            self.stack.setCurrentIndex(idx)

    @staticmethod
    def _item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    @staticmethod
    def _numeric_id_item(text: str) -> NumericSortTableItem:
        sort_val = int(text) if text.isdigit() else None
        item = NumericSortTableItem(text, sort_val)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    # ── slots ────────────────────────────────────────────────────────

    def _on_filter_changed(self):
        self.refresh()

    def _on_view_changed(self):
        self._sync_stack_to_view()

    def _on_double_click(self, index):
        row = index.row()
        id_item = self.table.item(row, 0)
        if id_item:
            try:
                award_id = int(id_item.text())
                self.award_selected.emit(award_id)
            except ValueError:
                pass

    def _on_create(self):
        dlg = CreateAwardDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                created = self.api.create_award(dlg.get_data())
                new_id = created.get("id")
                front, back = dlg.get_image_paths()
                if new_id and (front or back):
                    self.api.upload_award_images(int(new_id), front_path=front, back_path=back)
                self.refresh()
            except APIError as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать награду.\n{e}")

    def _on_delete(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Удаление", "Выберите награду для удаления.")
            return

        row = rows[0].row()
        name = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
        award_id_text = self.table.item(row, 0).text() if self.table.item(row, 0) else ""

        answer = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f'Удалить награду "{name}" (ID {award_id_text})?',
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self.api.delete_award(int(award_id_text))
            self.refresh()
        except (APIError, ValueError) as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить награду.\n{e}")
