import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QAbstractItemView, QScrollArea, QFrame,
    QGridLayout, QStackedWidget, QSizePolicy, QFileDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QFont, QImage, QPixmap

from api_client import APIClient, APIError
from ui.numeric_sort_item import NumericSortTableItem
from ui.fetch_worker import run_api_fetch, thread_api_call
from ui.awards_cache import AwardsCache

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


class _CatalogThumbLoader:
    MAX = 8
    _pending: list = []
    _active = 0

    @classmethod
    def clear(cls) -> None:
        cls._pending.clear()

    @classmethod
    def load(cls, award_id: int, has_front: bool, has_back: bool, callback, token: int) -> None:
        data = AwardsCache.get_catalog_image_bytes(award_id, has_front, has_back)
        if data is not None:
            callback(data, token)
            return
        cls.schedule(award_id, has_front, has_back, callback, token)

    @classmethod
    def schedule(cls, award_id: int, has_front: bool, has_back: bool, callback, token: int) -> None:
        cls._pending.append((award_id, has_front, has_back, callback, token))
        cls._drain()

    @classmethod
    def _drain(cls) -> None:
        if cls._active >= cls.MAX or not cls._pending:
            return
        cls._active += 1
        award_id, has_front, has_back, callback, token = cls._pending.pop(0)

        def fetch():
            def load_bytes(api):
                if has_front:
                    data = api.get_award_image_bytes(award_id, "front")
                    if data:
                        return data, "front"
                if has_back:
                    data = api.get_award_image_bytes(award_id, "back")
                    if data:
                        return data, "back"
                return None, None

            return thread_api_call(load_bytes)

        def done(result, t=token):
            cls._active -= 1
            data, side = result if isinstance(result, tuple) else (result, None)
            if data and side:
                AwardsCache.set_image_bytes(award_id, side, data)
            callback(data, t)
            cls._drain()

        def fail(_err, t=token):
            cls._active -= 1
            callback(None, t)
            cls._drain()

        run_api_fetch(fetch, lambda d: done(d, token), lambda e: fail(e, token))


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
        catalog_gen: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self._award_id = award_id
        self._api = api
        self._has_image = has_image
        self._has_image_back = has_image_back
        self._catalog_gen = catalog_gen
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

        if self._has_image or self._has_image_back:
            pm = AwardsCache.get_thumb_pixmap(
                self._award_id, self._has_image, self._has_image_back,
            )
            if pm is not None:
                self._img.setPixmap(pm)
            else:
                _CatalogThumbLoader.load(
                    self._award_id,
                    self._has_image,
                    self._has_image_back,
                    self._apply_thumb,
                    self._catalog_gen,
                )

    def _apply_thumb(self, data, token: int) -> None:
        if token != self._catalog_gen:
            return
        pm = QPixmap(160, 160)
        pm.fill(Qt.transparent)
        if data:
            p = QPixmap()
            if p.loadFromData(data):
                pm = p.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                img = QImage.fromData(data)
                if not img.isNull():
                    pm = QPixmap.fromImage(img).scaled(
                        160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation,
                    )
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
        self._refresh_gen = 0
        self._catalog_gen = 0
        self._last_applied_ids: tuple[int, ...] | None = None
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

    def apply_from_cache_only(self) -> bool:
        _, type_value = AWARD_TYPE_FILTER[self.filter_combo.currentIndex()]
        cached = AwardsCache.filter_awards(type_value)
        if cached is None:
            return False
        self._apply_awards_list(cached, self._refresh_gen)
        return True

    def refresh_data(self):
        self.refresh(force_network=True)

    # ── data loading ─────────────────────────────────────────────────

    def refresh(self, force_network: bool = False):
        _, type_value = AWARD_TYPE_FILTER[self.filter_combo.currentIndex()]
        if not force_network:
            cached = AwardsCache.filter_awards(type_value)
            if cached is not None:
                self._apply_awards_list(cached, self._refresh_gen)
                return
        self._fetch_from_network()

    def _fetch_from_network(self) -> None:
        self._refresh_gen += 1
        gen = self._refresh_gen
        _, type_value = AWARD_TYPE_FILTER[self.filter_combo.currentIndex()]

        def fetch():
            return thread_api_call(lambda api: api.get_awards(award_type=type_value))

        run_api_fetch(
            fetch,
            on_success=lambda awards: self._on_awards_fetched(awards, gen, type_value),
            on_error=lambda err: self._on_refresh_error(err, gen),
        )

    def _on_awards_fetched(self, awards, gen: int, type_value):
        if gen != self._refresh_gen:
            return
        awards = sorted(
            awards or [],
            key=lambda a: (
                str(a.get("name") or "").strip().lower(),
                int(a.get("id") or 0),
            ),
        )
        if not type_value:
            AwardsCache.set_awards_all(awards)
            AwardsCache.preload_missing_images(awards)
        self._apply_awards_list(awards, gen)

    def _on_refresh_error(self, err: str, gen: int):
        if gen != self._refresh_gen:
            return
        QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось загрузить награды.\n{err}")

    def _apply_awards_list(self, awards, gen: int):
        if gen != self._refresh_gen:
            return
        ids = tuple(int(a.get("id") or 0) for a in awards)
        if ids != self._last_applied_ids:
            self._last_applied_ids = ids
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
        if self._catalog_grid is None:
            return
        _CatalogThumbLoader.clear()
        self._catalog_gen += 1
        catalog_gen = self._catalog_gen
        while self._catalog_grid.count():
            item = self._catalog_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        cols = self.GRID_COLS
        if not awards:
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
        for i, award in enumerate(awards):
            aid = int(award.get("id", 0))
            name = str(award.get("name", ""))
            has_img = bool(award.get("has_image"))
            has_img_back = bool(award.get("has_image_back"))
            card = _AwardCatalogCard(
                aid, name, self.api,
                has_image=has_img,
                has_image_back=has_img_back,
                catalog_gen=catalog_gen,
                parent=self._catalog_inner,
            )
            card.clicked_id.connect(self.award_selected.emit)
            r, c = divmod(i, cols)
            self._catalog_grid.addWidget(card, r, c)

        if self._catalog_inner is not None:
            self._catalog_inner.adjustSize()
            self._catalog_inner.updateGeometry()
        if self._catalog_scroll is not None:
            self._catalog_scroll.updateGeometry()

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
        _, type_value = AWARD_TYPE_FILTER[self.filter_combo.currentIndex()]
        cached = AwardsCache.filter_awards(type_value)
        if cached is not None:
            self._apply_awards_list(cached, self._refresh_gen)
            return
        self.refresh(force_network=True)

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
                    AwardsCache.invalidate_award_images(int(new_id))
                self.refresh(force_network=True)
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
            AwardsCache.invalidate_award_images(int(award_id_text))
            self.refresh(force_network=True)
        except (APIError, ValueError) as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить награду.\n{e}")
