from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QFrame, QPushButton, QStatusBar,
    QScrollArea, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon

from api_client import APIClient, APIError

from ui.awards.awards_cards import AwardsCardsPage
from ui.awards.award_detail import AwardDetailPage
from ui.awards.lifecycle import LifecyclePage
from ui.awards.warehouse import WarehousePage
from ui.awards.current_awards_report import CurrentAwardsReportPage

from ui.laureates.laureate_cards import LaureateCardsPage
from ui.laureates.laureate_detail import LaureateDetailPage
from ui.laureates.laureate_lc import LaureateLifecyclePage
from ui.laureates.awards_laureates import AwardsLaureatesPage
from ui.laureates.incomplete_lc import IncompleteLCPage
from ui.laureates.statistics import StatisticsPage
from ui.laureates.lc_stages_report import LifecycleStagesReportPage

from ui.committee.committee_list import CommitteeListPage
from ui.committee.member_card import MemberCardPage

from ui.voting.bulletin import BulletinPage
from ui.voting.monitoring import MonitoringPage
from ui.voting.vote_counting import VoteCountingPage
from ui.voting.protocol import ProtocolPage
from ui.voting.extract import ExtractPage
from ui.voting.ppz_submission import PPZSubmissionPage

from ui.service.db_export import DBExportPage
from ui.service.access_tables_page import AccessTablesPage


# ── Navigation structure ────────────────────────────────────────────────────
# Each entry: ("section_header", None) or ("item_label", "page_key")
# A plain string "---" acts as a horizontal divider.

NAV_ITEMS = [
    ("НАГРАДЫ", None),
    ("Карточки наград", "award_cards"),
    ("Жизненный цикл наград", "award_lifecycle"),
    ("Склад", "warehouse"),
    ("Отчёт: актуальные награды", "current_awards_report"),

    ("ЛАУРЕАТЫ", None),
    ("Карточки лауреатов", "laureate_cards"),
    ("Награды-лауреаты", "awards_laureates"),
    ("Незавершённый ЖЦ", "incomplete_lifecycle"),
    ("Отчёт: этапы ЖЦ", "lifecycle_stages_report"),
    ("Статистика", "statistics"),

    ("НАГРАДНОЙ КОМИТЕТ", None),
    ("Список НК", "committee_list"),

    ("ГОЛОСОВАНИЕ", None),
    ("Бюллетени", "bulletins"),
    ("Мониторинг ответов", "monitoring"),
    ("Подсчёт голосов", "vote_results"),
    ("Протоколы", "protocols"),
    ("Выписки", "extracts"),
    ("Представления ППЗ", "ppz_submissions"),

    "---",

    ("СЕРВИС", None),
    ("Таблицы Access (как в бэкенде)", "access_mirror"),
    ("Выгрузка БД", "db_export"),
]


class SidebarButton(QPushButton):
    """Navigation button used inside the sidebar."""

    def __init__(self, text: str, page_key: str, parent=None):
        super().__init__(text, parent)
        self.page_key = page_key
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("class", "sidebar-item")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.api = APIClient()

        self.setWindowTitle("ООН ПКР — База данных наград")
        self.resize(1280, 800)
        self._center_on_screen()

        self._page_buttons: list[SidebarButton] = []
        self._pages: dict[str, int] = {}
        self._award_widgets: dict[str, QWidget] = {}

        self._build_ui()
        self._build_status_bar()
        self._start_health_timer()

    # ── geometry ────────────────────────────────────────────────────────

    def _center_on_screen(self):
        frame = self.frameGeometry()
        screen_center = self.screen().availableGeometry().center()
        frame.moveCenter(screen_center)
        self.move(frame.topLeft())

    # ── UI assembly ─────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.stack.setProperty("class", "content-area")
        root_layout.addWidget(self.stack, 1)

        self._populate_sidebar_and_pages()
        self._build_award_detail_page()
        self._build_laureate_detail_pages()
        self._build_member_card_page()

        if self._page_buttons:
            self._select_page(self._page_buttons[0].page_key)

    # ── sidebar ---------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebar")
        sidebar_frame.setFixedWidth(220)

        self._sidebar_layout = QVBoxLayout(sidebar_frame)
        self._sidebar_layout.setContentsMargins(0, 12, 0, 12)
        self._sidebar_layout.setSpacing(0)

        title = QLabel("ООН ПКР")
        title.setObjectName("sidebar-title")
        title.setAlignment(Qt.AlignCenter)
        self._sidebar_layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setObjectName("sidebar-scroll")

        scroll_content = QWidget()
        self._nav_layout = QVBoxLayout(scroll_content)
        self._nav_layout.setContentsMargins(0, 8, 0, 8)
        self._nav_layout.setSpacing(1)

        scroll_area.setWidget(scroll_content)
        self._sidebar_layout.addWidget(scroll_area, 1)

        return sidebar_frame

    def _populate_sidebar_and_pages(self):
        for entry in NAV_ITEMS:
            if entry == "---":
                divider = QFrame()
                divider.setFrameShape(QFrame.HLine)
                divider.setProperty("class", "sidebar-divider")
                self._nav_layout.addWidget(divider)
                continue

            label_text, page_key = entry

            if page_key is None:
                header = QLabel(label_text)
                header.setProperty("class", "sidebar-header")
                self._nav_layout.addWidget(header)
            else:
                btn = SidebarButton(label_text, page_key)
                btn.clicked.connect(lambda checked, k=page_key: self._select_page(k))
                self._nav_layout.addWidget(btn)
                self._page_buttons.append(btn)

                page_widget = self._create_page(page_key, label_text)
                idx = self.stack.addWidget(page_widget)
                self._pages[page_key] = idx

        self._nav_layout.addStretch(1)

    def _create_page(self, page_key: str, label_text: str) -> QWidget:
        """Return a real page widget for known keys, placeholder otherwise."""
        if page_key == "award_cards":
            page = AwardsCardsPage(self.api)
            page.award_selected.connect(self._open_award_detail)
            self._award_widgets[page_key] = page
            return page

        if page_key == "award_lifecycle":
            page = LifecyclePage(self.api)
            page.award_selected.connect(self._open_award_detail)
            self._award_widgets[page_key] = page
            return page

        if page_key == "warehouse":
            page = WarehousePage(self.api)
            self._award_widgets[page_key] = page
            return page

        if page_key == "current_awards_report":
            return CurrentAwardsReportPage(self.api)

        if page_key == "laureate_cards":
            page = LaureateCardsPage(self.api)
            page.laureate_selected.connect(self._open_laureate_detail)
            return page

        if page_key == "awards_laureates":
            page = AwardsLaureatesPage(self.api)
            page.open_lifecycle.connect(self._open_laureate_lifecycle)
            return page

        if page_key == "incomplete_lifecycle":
            page = IncompleteLCPage(self.api)
            page.open_lifecycle.connect(self._open_laureate_lifecycle)
            return page

        if page_key == "lifecycle_stages_report":
            page = LifecycleStagesReportPage(self.api)
            page.open_lifecycle.connect(self._open_laureate_lifecycle)
            return page

        if page_key == "statistics":
            return StatisticsPage(self.api)

        if page_key == "committee_list":
            page = CommitteeListPage(self.api)
            page.member_selected.connect(self._open_member_card)
            return page

        if page_key == "bulletins":
            return BulletinPage(self.api)

        if page_key == "monitoring":
            return MonitoringPage(self.api)

        if page_key == "vote_results":
            return VoteCountingPage(self.api)

        if page_key == "protocols":
            return ProtocolPage(self.api)

        if page_key == "extracts":
            return ExtractPage(self.api)

        if page_key == "ppz_submissions":
            return PPZSubmissionPage(self.api)

        if page_key == "access_mirror":
            return AccessTablesPage(self.api)

        if page_key == "db_export":
            return DBExportPage(self.api)

        return self._make_placeholder_page(label_text)

    # ── award detail (hidden page, not in sidebar) ───────────────────

    def _build_award_detail_page(self):
        self._award_detail = AwardDetailPage(self.api)
        self._award_detail.go_back.connect(self._close_award_detail)
        self._award_detail_idx = self.stack.addWidget(self._award_detail)

    def _open_award_detail(self, award_id: int):
        if not self._maybe_confirm_unsaved_on_leave():
            return
        self._award_detail.load_award(award_id)
        self.stack.setCurrentIndex(self._award_detail_idx)
        for btn in self._page_buttons:
            btn.setChecked(False)

    def _close_award_detail(self):
        self._select_page("award_cards")

    # ── laureate detail / lifecycle (hidden pages, not in sidebar) ────────

    def _build_laureate_detail_pages(self):
        self._laureate_detail = LaureateDetailPage(self.api)
        self._laureate_detail.back_requested.connect(self._close_laureate_detail)
        self._laureate_detail.open_lifecycle.connect(self._open_laureate_lifecycle)
        self._laureate_detail_idx = self.stack.addWidget(self._laureate_detail)

        self._laureate_lc = LaureateLifecyclePage(self.api)
        self._laureate_lc.back_requested.connect(self._close_laureate_lifecycle)
        self._laureate_lc_idx = self.stack.addWidget(self._laureate_lc)

        self._lc_return_page: str = "laureate_cards"

    def _open_laureate_detail(self, laureate_id: int):
        if not self._maybe_confirm_unsaved_on_leave():
            return
        self._laureate_detail.load_laureate(laureate_id)
        self.stack.setCurrentIndex(self._laureate_detail_idx)
        for btn in self._page_buttons:
            btn.setChecked(False)

    def _close_laureate_detail(self):
        self._select_page("laureate_cards")
        page = self.stack.widget(self._pages.get("laureate_cards", 0))
        if hasattr(page, "refresh_data"):
            page.refresh_data()

    def _open_laureate_lifecycle(self, laureate_award_id: int):
        if not self._maybe_confirm_unsaved_on_leave():
            return
        current_idx = self.stack.currentIndex()
        if current_idx == self._laureate_detail_idx:
            self._lc_return_page = "__detail__"
        else:
            self._lc_return_page = "laureate_cards"
            for key, idx in self._pages.items():
                if idx == current_idx:
                    self._lc_return_page = key
                    break
        self._laureate_lc.load_lifecycle(laureate_award_id)
        self.stack.setCurrentIndex(self._laureate_lc_idx)
        for btn in self._page_buttons:
            btn.setChecked(False)

    def _close_laureate_lifecycle(self):
        if self.stack.currentIndex() == self._laureate_lc_idx:
            if self._lc_return_page == "__detail__":
                self.stack.setCurrentIndex(self._laureate_detail_idx)
            else:
                self._select_page(self._lc_return_page)

    # ── committee member card (hidden page) ──────────────────────────────

    def _build_member_card_page(self):
        self._member_card = MemberCardPage(self.api)
        self._member_card.back_requested.connect(self._close_member_card)
        self._member_card_idx = self.stack.addWidget(self._member_card)

    def _open_member_card(self, member_id: int):
        if not self._maybe_confirm_unsaved_on_leave():
            return
        self._member_card.load_member(member_id)
        self.stack.setCurrentIndex(self._member_card_idx)
        for btn in self._page_buttons:
            btn.setChecked(False)

    def _close_member_card(self):
        self._select_page("committee_list")
        page = self.stack.widget(self._pages.get("committee_list", 0))
        if hasattr(page, "refresh_data"):
            page.refresh_data()

    # ── page switching ---------------------------------------------------

    def _maybe_confirm_unsaved_on_leave(self) -> bool:
        """Prevent losing edits when opening another page/dialog."""
        current_idx = self.stack.currentIndex()
        if current_idx == getattr(self, "_award_detail_idx", -1):
            return self._award_detail.confirm_quit_application()
        if current_idx == getattr(self, "_laureate_detail_idx", -1):
            return self._laureate_detail.confirm_quit_application()
        if current_idx == getattr(self, "_laureate_lc_idx", -1):
            return self._laureate_lc.confirm_quit_application()
        return True

    def _select_page(self, page_key: str):
        # Guard: do not lose unsaved changes when navigating via sidebar.
        if not self._maybe_confirm_unsaved_on_leave():
            return

        idx = self._pages.get(page_key)
        if idx is None:
            return
        self.stack.setCurrentIndex(idx)
        for btn in self._page_buttons:
            btn.setChecked(btn.page_key == page_key)

    # ── placeholder pages ------------------------------------------------

    @staticmethod
    def _make_placeholder_page(section_name: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel(f"Раздел: {section_name}")
        title.setProperty("class", "page-title")
        layout.addWidget(title)

        hint = QLabel("Содержимое раздела будет добавлено позднее.")
        hint.setProperty("class", "page-hint")
        layout.addWidget(hint)

        layout.addStretch(1)
        return page

    # ── status bar -------------------------------------------------------

    def _build_status_bar(self):
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._conn_label = QLabel()
        self._conn_label.setProperty("class", "status-label")
        self._status_bar.addPermanentWidget(self._conn_label)

        self._set_connection_status(False)

    def _set_connection_status(self, connected: bool):
        if connected:
            self._conn_label.setText("● Подключено к серверу")
            self._conn_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self._conn_label.setText("● Нет соединения")
            self._conn_label.setStyleSheet("color: #F44336; font-weight: bold;")

    # ── health check timer -----------------------------------------------

    def _start_health_timer(self):
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_health)
        self._health_timer.start(5000)
        self._check_health()

    def _check_health(self):
        try:
            resp = self.api.health_check()
            self._set_connection_status(resp.get("status") == "ok")
        except Exception:
            self._set_connection_status(False)

    # ── cleanup ----------------------------------------------------------

    def closeEvent(self, event):
        idx = self.stack.currentIndex()
        if idx == self._award_detail_idx:
            if not self._award_detail.confirm_quit_application():
                event.ignore()
                return
        elif idx == self._laureate_detail_idx:
            if not self._laureate_detail.confirm_quit_application():
                event.ignore()
                return
        elif idx == self._laureate_lc_idx:
            if not self._laureate_lc.confirm_quit_application():
                event.ignore()
                return

        self._health_timer.stop()
        self.api.close()
        super().closeEvent(event)
