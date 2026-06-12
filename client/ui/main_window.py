from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QFrame, QPushButton, QStatusBar,
    QScrollArea, QSizePolicy, QButtonGroup, QProgressBar, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon

from api_client import APIClient, APIError

from ui.fetch_worker import activity as fetch_activity, run_api_fetch, thread_api_call
from ui.laureates_cache import LaureatesCache
from ui.awards_cache import AwardsCache
from ui.app_cache import AppCache

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
from ui.laureates.awards_bulletins import AwardsBulletinsPage

from ui.committee.committee_list import CommitteeListPage
from ui.committee.member_card import MemberCardPage
from ui.committee.approvals_monitor import ApprovalsMonitorPage

from ui.voting.bulletin import BulletinPage
from ui.voting.monitoring import MonitoringPage
from ui.voting.vote_counting import VoteCountingPage
from ui.voting.protocol import ProtocolPage
from ui.voting.extract import ExtractPage
from ui.voting.ppz_submission import PPZSubmissionPage

from ui.service.db_export import DBExportPage
from ui.service.access_tables_page import AccessTablesPage
from ui.help_installer import install_help_for_page
from ui.connection_state import connection_state
from ui.draft_store import flush_all, list_pending_drafts


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
    ("Награды-бюллетени", "awards_bulletins"),
    ("Незавершённый ЖЦ", "incomplete_lifecycle"),
    ("Отчёт: этапы ЖЦ", "lifecycle_stages_report"),
    ("Статистика", "statistics"),

    ("НАГРАДНОЙ КОМИТЕТ", None),
    ("Список НК", "committee_list"),
    ("Мониторинг согласований", "approvals_monitor"),

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
        self.setMinimumSize(960, 640)
        self.resize(1280, 800)
        self._center_on_screen()

        self._page_buttons: list[SidebarButton] = []
        self._nav_button_group = QButtonGroup(self)
        self._nav_button_group.setExclusive(True)
        self._pages: dict[str, int] = {}
        self._award_widgets: dict[str, QWidget] = {}
        self._nav_generation = 0
        self._pages_loaded: set[str] = set()
        self._awaiting_preload: dict[str, QWidget] = {}
        self._warm_queue: list[str] = []
        self._warm_pass = 0
        self._offline_banner_warned = False
        self._connection_lost_in_session = False
        self._initial_health_pending = True

        self._build_ui()
        self._load_cache_and_preload()
        self._build_status_bar()
        connection_state.changed.connect(self._on_connection_changed)
        self._start_health_timer()

    _PAGE_TO_CACHE = {
        "laureate_cards": "laureates",
        "awards_laureates": "awards_laureates",
        "incomplete_lifecycle": "incomplete_lifecycle",
        "lifecycle_stages_report": "lifecycle_by_stage",
        "statistics": "statistics_all",
        "award_cards": "awards_all",
        "current_awards_report": "awards_all",
        "award_lifecycle": "award_lifecycle",
        "warehouse": "warehouse",
        "committee_list": "committee_members",
    }

    _AWARD_PRELOAD_MAP = {
        "awards_all": ("award_cards", "current_awards_report"),
        "award_lifecycle": ("award_lifecycle",),
        "warehouse": ("warehouse",),
    }

    _APP_PRELOAD_MAP = {
        "committee_members": ("committee_list",),
    }

    _WARMABLE_PAGE_KEYS = (
        "award_cards",
        "award_lifecycle",
        "warehouse",
        "current_awards_report",
        "laureate_cards",
        "awards_laureates",
        "incomplete_lifecycle",
        "lifecycle_stages_report",
        "statistics",
        "committee_list",
    )

    def _load_cache_and_preload(self) -> None:
        """Кэш с диска — в фоне, затем preload разделов «Награды» и «Лауреаты»."""
        LaureatesCache.mark_preload_start({
            "laureates",
            "awards_laureates",
            "incomplete_lifecycle",
            "lifecycle_by_stage",
            "statistics_all",
        })
        AwardsCache.mark_preload_start({
            "awards_all",
            "award_lifecycle",
            "warehouse",
        })
        AppCache.mark_preload_start({"committee_members"})

        def load_disk():
            LaureatesCache.load_from_disk()
            AwardsCache.load_from_disk()
            AppCache.load_from_disk()
            return True

        run_api_fetch(
            load_disk,
            on_success=lambda _ok: self._on_disk_cache_ready(),
            on_error=lambda _err: self._on_disk_cache_ready(),
        )

    def _on_disk_cache_ready(self) -> None:
        """Кэш с диска готов — сразу прогреть UI, параллельно обновить данные с сервера."""
        AwardsCache.preload_missing_images()
        self._schedule_warm_pages()
        self._start_laureates_preload()
        self._start_awards_preload()
        self._start_app_preload()

    def _start_app_preload(self) -> None:
        jobs = [
            ("committee_members", lambda api: api.get_committee_members(is_active=None)),
        ]
        for name, fetch in jobs:
            run_api_fetch(
                lambda f=fetch: thread_api_call(f),
                on_success=lambda data, n=name: self._on_app_preload_ok(n, data),
                on_error=lambda _err, n=name: self._on_app_preload_error(n),
            )

    def _on_app_preload_error(self, name: str) -> None:
        AppCache.mark_preload_done(name)
        self._finish_awaiting_preload(name, app=True)
        self._check_all_preload_done()

    def _on_app_preload_ok(self, name: str, data) -> None:
        if name == "committee_members":
            AppCache.set_committee_members(data)
        AppCache.mark_preload_done(name)
        self._finish_awaiting_preload(name, app=True)
        self._check_all_preload_done()

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

        content_wrap = QWidget()
        content_col = QVBoxLayout(content_wrap)
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(0)

        self._offline_banner = self._build_offline_banner()
        self._offline_banner.hide()
        content_col.addWidget(self._offline_banner)

        self.stack = QStackedWidget()
        self.stack.setProperty("class", "content-area")
        content_col.addWidget(self.stack, 1)

        root_layout.addWidget(content_wrap, 1)

        self._populate_sidebar_and_pages()
        self._build_award_detail_page()
        self._build_laureate_detail_pages()
        self._build_member_card_page()

        if self._page_buttons:
            self._select_page(self._page_buttons[0].page_key)

    _LAUREATE_PAGE_KEYS = (
        "laureate_cards",
        "awards_laureates",
        "incomplete_lifecycle",
        "lifecycle_stages_report",
        "statistics",
    )

    _LAUREATE_PRELOAD_MAP = {
        "laureates": "laureate_cards",
        "awards_laureates": "awards_laureates",
        "incomplete_lifecycle": "incomplete_lifecycle",
        "lifecycle_by_stage": "lifecycle_stages_report",
        "statistics_all": "statistics",
    }

    def _start_awards_preload(self) -> None:
        """Фоновое обновление кэша раздела «Награды» при старте."""
        jobs = [
            ("awards_all", lambda api: api.get_awards()),
            ("award_lifecycle", lambda api: api.get_award_lifecycle_report()),
            ("warehouse", lambda api: api.get_warehouse_report()),
        ]
        for name, fetch in jobs:
            run_api_fetch(
                lambda f=fetch: thread_api_call(f),
                on_success=lambda data, n=name: self._on_awards_preload_ok(n, data),
                on_error=lambda _err, n=name: self._on_awards_preload_error(n),
            )

    def _on_awards_preload_error(self, name: str) -> None:
        AwardsCache.mark_preload_done(name)
        self._finish_awaiting_preload(name, awards=True)
        self._check_all_preload_done()

    def _on_awards_preload_ok(self, name: str, data) -> None:
        if name == "awards_all":
            AwardsCache.set_awards_all(data or [])
            AwardsCache.preload_missing_images(data or [])
        elif name == "award_lifecycle":
            AwardsCache.set_award_lifecycle(data)
        elif name == "warehouse":
            AwardsCache.set_warehouse(data)
        AwardsCache.mark_preload_done(name)
        self._finish_awaiting_preload(name, awards=True)
        self._check_all_preload_done()

    def _start_laureates_preload(self) -> None:
        """Фоновое обновление кэша раздела «Лауреаты» при старте."""
        jobs = [
            ("laureates", lambda api: api.get_laureates()),
            ("awards_laureates", lambda api: api.report_awards_laureates()),
            ("incomplete_lifecycle", lambda api: api.report_incomplete_lifecycle()),
            ("lifecycle_by_stage", lambda api: api.report_lifecycle_by_stage()),
            ("statistics_all", lambda api: api.report_statistics(from_date=None, to_date=None)),
        ]
        for name, fetch in jobs:
            run_api_fetch(
                lambda f=fetch: thread_api_call(f),
                on_success=lambda data, n=name: self._on_laureate_preload_ok(n, data),
                on_error=lambda _err, n=name: self._on_laureate_preload_error(n),
            )

    def _on_laureate_preload_error(self, name: str) -> None:
        LaureatesCache.mark_preload_done(name)
        self._finish_awaiting_preload(name)
        self._check_all_preload_done()

    def _on_laureate_preload_ok(self, name: str, data) -> None:
        if name == "laureates":
            LaureatesCache.set_laureates(data)
        elif name == "awards_laureates":
            LaureatesCache.set_awards_laureates(data)
        elif name == "incomplete_lifecycle":
            LaureatesCache.set_incomplete_lifecycle(data)
        elif name == "lifecycle_by_stage":
            LaureatesCache.set_lifecycle_by_stage(data)
        elif name == "statistics_all":
            if isinstance(data, dict):
                LaureatesCache.set_statistics_all(data.get("by_category") or [])
            else:
                LaureatesCache.set_statistics_all(data or [])

        LaureatesCache.mark_preload_done(name)
        self._finish_awaiting_preload(name)
        self._check_all_preload_done()

    def _finish_awaiting_preload(
        self,
        cache_name: str,
        *,
        awards: bool = False,
        app: bool = False,
    ) -> None:
        if app:
            page_keys = self._APP_PRELOAD_MAP.get(cache_name, ())
        elif awards:
            page_keys = self._AWARD_PRELOAD_MAP.get(cache_name, ())
        else:
            page_key = self._LAUREATE_PRELOAD_MAP.get(cache_name)
            page_keys = (page_key,) if page_key else ()

        for page_key in page_keys:
            if page_key is None:
                continue
            waiting = self._awaiting_preload.pop(page_key, None)
            if waiting is not None:
                self._warm_page(page_key, widget=waiting)
                continue
            if page_key in self._pages_loaded:
                continue
            idx = self._pages.get(page_key)
            if idx is None or self.stack.currentIndex() != idx:
                continue
            widget = self.stack.widget(idx)
            if widget is not None:
                self._warm_page(page_key, widget=widget)

    def _all_preload_done(self) -> bool:
        return (
            not LaureatesCache.preload_pending
            and not AwardsCache.preload_pending
            and not AppCache.preload_pending
        )

    def _check_all_preload_done(self) -> None:
        if not self._all_preload_done():
            return
        AwardsCache.preload_missing_images()
        self._schedule_warm_pages()

    def _warm_page(self, page_key: str, widget: QWidget | None = None) -> bool:
        if widget is None:
            idx = self._pages.get(page_key)
            if idx is None:
                return False
            widget = self.stack.widget(idx)
        if widget is None:
            return False
        apply_fn = getattr(widget, "apply_from_cache_only", None)
        if callable(apply_fn) and apply_fn():
            self._pages_loaded.add(page_key)
            relayout = getattr(widget, "schedule_catalog_relayout", None)
            if callable(relayout):
                relayout()
            return True
        return False

    def _schedule_warm_pages(self, page_keys: tuple[str, ...] | None = None) -> None:
        """Порциями заполнить все страницы из кэша (не блокируя UI)."""
        keys = list(page_keys or self._WARMABLE_PAGE_KEYS)
        self._warm_queue = keys
        self._warm_pass += 1
        warm_pass = self._warm_pass
        QTimer.singleShot(0, lambda: self._warm_next_page(warm_pass))

    def _warm_next_page(self, warm_pass: int) -> None:
        if warm_pass != self._warm_pass or not self._warm_queue:
            if warm_pass == self._warm_pass:
                self._warm_queue = []
            return
        page_key = self._warm_queue.pop(0)
        self._warm_page(page_key)
        if self._warm_queue and warm_pass == self._warm_pass:
            QTimer.singleShot(0, lambda: self._warm_next_page(warm_pass))

    def _build_offline_banner(self) -> QWidget:
        bar = QWidget()
        bar.setProperty("class", "offline-banner")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 8, 12, 8)
        self._offline_banner_label = QLabel(
            "Нет связи с сервером. Доступен просмотр ранее загруженных данных; "
            "сохранение и изменения временно недоступны.",
        )
        self._offline_banner_label.setWordWrap(True)
        row.addWidget(self._offline_banner_label, 1)
        btn_check = QPushButton("Проверить связь")
        btn_check.setProperty("class", "btn-secondary")
        btn_check.clicked.connect(self._check_health)
        row.addWidget(btn_check)
        return bar

    def _apply_connection_ui(self, online: bool) -> None:
        self._update_connection_label(online)
        show_banner = not online
        self._offline_banner.setVisible(show_banner)
        if show_banner and self._initial_health_pending:
            self._offline_banner_label.setText(
                "Проверка связи с сервером… Сохранение и изменения временно недоступны.",
            )
        elif show_banner:
            self._offline_banner_label.setText(
                "Нет связи с сервером. Доступен просмотр ранее загруженных данных; "
                "сохранение и изменения временно недоступны.",
            )
        if online:
            QTimer.singleShot(200, self._relayout_current_content_page)

    def _maybe_warn_offline(self) -> None:
        if self._offline_banner_warned or self._initial_health_pending:
            return
        self._offline_banner_warned = True
        pending = len(list_pending_drafts())
        extra = ""
        if pending:
            extra = (
                f"\n\nЛокальных черновиков: {pending} — "
                "отправятся после восстановления связи."
            )
        QMessageBox.warning(
            self,
            "Связь с сервером потеряна",
            "Работа без сервера: можно просматривать кэшированные списки, "
            "но сохранять и создавать записи нельзя."
            + extra,
        )

    def _relayout_current_content_page(self) -> None:
        idx = self.stack.currentIndex()
        widget = self.stack.widget(idx)
        if widget is None:
            return
        fn = getattr(widget, "schedule_catalog_relayout", None)
        if callable(fn):
            fn()

    def _on_connection_changed(self, online: bool) -> None:
        self._apply_connection_ui(online)
        if online:
            if self._connection_lost_in_session:
                self._connection_lost_in_session = False
                self._offline_banner_warned = False
                self._on_connection_restored()
        else:
            if connection_state.ever_online:
                self._connection_lost_in_session = True
            self._maybe_warn_offline()

    def _on_connection_restored(self) -> None:
        ok, errors = flush_all(self.api)
        msg = "Связь с сервером восстановлена."
        if ok:
            msg += f"\n\nОтправлено черновиков на сервер: {ok}."
            self._refresh_current_page()
        if errors:
            msg += "\n\nНе удалось отправить:\n• " + "\n• ".join(errors[:5])
        if ok or errors:
            msg += "\n\nРекомендуется нажать «Обновить» на текущей странице."
        QMessageBox.information(self, "Сервер снова доступен", msg)

    def _refresh_current_page(self) -> None:
        idx = self.stack.currentIndex()
        for key, page_idx in self._pages.items():
            if page_idx == idx:
                widget = self.stack.widget(idx)
                if widget and hasattr(widget, "refresh_data"):
                    widget.refresh_data()
                return
        widget = self.stack.widget(idx)
        if widget and hasattr(widget, "refresh_data"):
            widget.refresh_data()

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
                self._nav_button_group.addButton(btn)
                btn.clicked.connect(lambda checked, k=page_key: self._select_page(k))
                self._nav_layout.addWidget(btn)
                self._page_buttons.append(btn)

                page_widget = self._create_page(page_key, label_text)
                install_help_for_page(page_widget, page_key)
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
            page.open_lifecycle.connect(self._open_laureate_lifecycle)
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

        if page_key == "awards_bulletins":
            page = AwardsBulletinsPage(self.api)
            page.open_lifecycle.connect(self._open_laureate_lifecycle)
            page.open_bulletin.connect(self._open_bulletin_by_number)
            return page

        if page_key == "incomplete_lifecycle":
            page = IncompleteLCPage(self.api)
            page.open_lifecycle.connect(self._open_laureate_lifecycle)
            page.open_bulletin.connect(self._open_bulletin_by_number)
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

        if page_key == "approvals_monitor":
            page = ApprovalsMonitorPage(self.api)
            page.award_selected.connect(self._open_award_detail)
            return page

        if page_key == "bulletins":
            page = BulletinPage(self.api)
            page.data_changed.connect(self._on_voting_data_changed)
            return page

        if page_key == "monitoring":
            page = MonitoringPage(self.api)
            page.enter_results_requested.connect(self._open_vote_counting_for_bulletin)
            return page

        if page_key == "vote_results":
            return VoteCountingPage(self.api)

        if page_key == "protocols":
            page = ProtocolPage(self.api)
            page.data_changed.connect(lambda: self._refresh_pages("extracts"))
            return page

        if page_key == "extracts":
            return ExtractPage(self.api)

        if page_key == "ppz_submissions":
            page = PPZSubmissionPage(self.api)
            page.assign_authorized_requested.connect(self._open_ppz_assign_authorized)
            return page

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
        install_help_for_page(self._award_detail, "award_detail")

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
        install_help_for_page(self._laureate_detail, "laureate_detail")
        install_help_for_page(self._laureate_lc, "laureate_lifecycle")

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

    def _open_vote_counting_for_bulletin(self, bulletin_id: int):
        """Переход из мониторинга на «Подсчёт голосов» с выбранным бюллетенем."""
        self._select_page("vote_results")
        idx = self._pages.get("vote_results")
        if idx is None:
            return
        page = self.stack.widget(idx)
        if page is not None and hasattr(page, "select_bulletin"):
            page.select_bulletin(bulletin_id)

    def _open_bulletin_by_number(self, number: str):
        """Переход из «Незав. ЖЦ» к бюллетеню по номеру."""
        if not self._maybe_confirm_unsaved_on_leave():
            return
        self._select_page("bulletins")
        idx = self._pages.get("bulletins")
        if idx is None:
            return
        page = self.stack.widget(idx)
        if page is not None and hasattr(page, "focus_bulletin_number"):
            page.focus_bulletin_number(number)

    # ── committee member card (hidden page) ──────────────────────────────

    def _build_member_card_page(self):
        self._member_card = MemberCardPage(self.api)
        self._member_card.back_requested.connect(self._close_member_card)
        self._member_card_idx = self.stack.addWidget(self._member_card)
        self._nk_return_page: str | None = None
        install_help_for_page(self._member_card, "member_card")

    def _open_member_card(self, member_id: int):
        if not self._maybe_confirm_unsaved_on_leave():
            return
        self._member_card.load_member(member_id)
        self.stack.setCurrentIndex(self._member_card_idx)
        for btn in self._page_buttons:
            btn.setChecked(False)

    def _open_ppz_assign_authorized(self, award_id: int, award_name: str):
        """Из «Представления ППЗ» — назначить уполномоченного по награде."""
        if not self._maybe_confirm_unsaved_on_leave():
            return
        self._nk_return_page = "ppz_submissions"
        self._select_page("committee_list")
        for btn in self._page_buttons:
            btn.setChecked(False)
        label = award_name or f"ID {award_id}"
        QMessageBox.information(
            self,
            "Назначение уполномоченного",
            f"Награда: {label}\n\n"
            "1. Выберите члена наградного комитета в списке.\n"
            "2. Откройте карточку (двойной щелчок или «Назначить уполномоченным»).\n"
            "3. В блоке «Уполномоченный по наградам» нажмите «Добавить» "
            "и выберите эту награду.\n"
            "4. Вернитесь «Назад» — откроется снова раздел «Представления ППЗ».",
        )

    def _close_member_card(self):
        if self._nk_return_page:
            ret = self._nk_return_page
            self._nk_return_page = None
            self._select_page(ret)
            idx = self._pages.get(ret)
            if idx is not None:
                page = self.stack.widget(idx)
                if page is not None and hasattr(page, "refresh_data"):
                    page.refresh_data()
            return
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

    def _refresh_page_widget(self, widget: QWidget | None) -> None:
        if widget is None:
            return
        for method_name in ("refresh_data", "load_data", "refresh"):
            method = getattr(widget, method_name, None)
            if callable(method):
                method()
                return

    def _sync_sidebar_checks(self) -> None:
        idx = self.stack.currentIndex()
        active_key = None
        for key, page_idx in self._pages.items():
            if page_idx == idx:
                active_key = key
                break
        self._nav_button_group.blockSignals(True)
        for btn in self._page_buttons:
            btn.setChecked(btn.page_key == active_key)
        self._nav_button_group.blockSignals(False)

    def _refresh_pages(self, *page_keys: str) -> None:
        for key in page_keys:
            idx = self._pages.get(key)
            if idx is not None:
                self._refresh_page_widget(self.stack.widget(idx))

    def _on_voting_data_changed(self) -> None:
        """После удаления бюллетеня — обновить связанные разделы голосования."""
        self._refresh_pages(
            "monitoring",
            "vote_results",
            "protocols",
            "extracts",
            "ppz_submissions",
        )

    def _select_page(self, page_key: str):
        if not self._maybe_confirm_unsaved_on_leave():
            self._sync_sidebar_checks()
            return

        ret = getattr(self, "_nk_return_page", None)
        if ret:
            if page_key == ret:
                self._nk_return_page = None
            elif page_key != "committee_list":
                self._nk_return_page = None

        idx = self._pages.get(page_key)
        if idx is None:
            return

        self._nav_generation += 1
        generation = self._nav_generation

        self.stack.setCurrentIndex(idx)
        self._nav_button_group.blockSignals(True)
        for btn in self._page_buttons:
            btn.setChecked(btn.page_key == page_key)
        self._nav_button_group.blockSignals(False)

        widget = self.stack.widget(idx)
        QTimer.singleShot(
            0,
            lambda w=widget, g=generation, k=page_key: self._deferred_page_refresh(w, g, k),
        )

    def _deferred_page_refresh(self, widget: QWidget | None, generation: int, page_key: str) -> None:
        if generation != self._nav_generation:
            return
        if widget is None:
            return

        # Уполномоченные могли назначить в НК без кнопки «Назад» — всегда обновлять.
        if page_key == "ppz_submissions":
            if hasattr(widget, "refresh_data"):
                widget.refresh_data()
            self._pages_loaded.add(page_key)
            return

        if page_key in self._pages_loaded:
            return

        apply_fn = getattr(widget, "apply_from_cache_only", None)
        if callable(apply_fn) and apply_fn():
            self._pages_loaded.add(page_key)
            return

        cache_key = self._PAGE_TO_CACHE.get(page_key)
        if cache_key and (
            cache_key in LaureatesCache.preload_pending
            or cache_key in AwardsCache.preload_pending
            or cache_key in AppCache.preload_pending
        ):
            self._awaiting_preload[page_key] = widget
            self._show_page_loading_hint(widget)
            return

        self._refresh_page_widget(widget)
        self._pages_loaded.add(page_key)

    @staticmethod
    def _show_page_loading_hint(widget: QWidget) -> None:
        for attr in ("status_label", "count_label", "total_label"):
            lbl = getattr(widget, attr, None)
            if lbl is not None and hasattr(lbl, "setText"):
                lbl.setText("Загрузка данных…")
                return

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

        self._loading_label = QLabel("Загрузка данных…")
        self._loading_label.setProperty("class", "status-label")
        self._loading_label.hide()

        self._loading_bar = QProgressBar()
        self._loading_bar.setFixedWidth(140)
        self._loading_bar.setFixedHeight(14)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setRange(0, 0)
        self._loading_bar.hide()

        self._conn_label = QLabel()
        self._conn_label.setProperty("class", "status-label")

        self._btn_check_conn = QPushButton("Проверить связь")
        self._btn_check_conn.setProperty("class", "status-bar-btn")
        self._btn_check_conn.setFixedHeight(22)
        self._btn_check_conn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._btn_check_conn.clicked.connect(self._check_health)

        self._status_bar.addPermanentWidget(self._loading_label)
        self._status_bar.addPermanentWidget(self._loading_bar)
        self._status_bar.addPermanentWidget(self._btn_check_conn)
        self._status_bar.addPermanentWidget(self._conn_label)

        fetch_activity.changed.connect(self._on_fetch_activity)
        self._conn_label.setText("○ Проверка связи…")
        self._conn_label.setStyleSheet("color: #888888; font-weight: bold;")

    def _on_fetch_activity(self, count: int) -> None:
        loading = count > 0
        self._loading_bar.setVisible(loading)
        self._loading_label.setVisible(loading)
        if loading:
            self._loading_label.setText(
                f"Загрузка данных… ({count})" if count > 1 else "Загрузка данных…",
            )

    def _update_connection_label(self, connected: bool):
        if connected:
            self._conn_label.setText("● Подключено к серверу")
            self._conn_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        elif self._initial_health_pending:
            self._conn_label.setText("○ Проверка связи…")
            self._conn_label.setStyleSheet("color: #888888; font-weight: bold;")
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
        def fetch():
            return thread_api_call(lambda api: api.health_check())

        def on_ok(resp):
            online = resp.get("status") == "ok" and resp.get("database") == "ok"
            self._initial_health_pending = False
            connection_state.set_online(online)

        def on_err(_err):
            self._initial_health_pending = False
            connection_state.set_online(False)

        run_api_fetch(fetch, on_success=on_ok, on_error=on_err)

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
