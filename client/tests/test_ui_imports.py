"""
Статические smoke-тесты UI без создания QApplication (стабильно на Windows/CI).
"""
from __future__ import annotations

import importlib
import inspect

import pytest

from ui.main_window import NAV_ITEMS

PAGE_MODULES = [
    "ui.awards.awards_cards",
    "ui.awards.lifecycle",
    "ui.awards.warehouse",
    "ui.awards.current_awards_report",
    "ui.awards.award_detail",
    "ui.laureates.laureate_cards",
    "ui.laureates.laureate_detail",
    "ui.laureates.laureate_lc",
    "ui.laureates.awards_laureates",
    "ui.laureates.incomplete_lc",
    "ui.laureates.lc_stages_report",
    "ui.laureates.statistics",
    "ui.committee.committee_list",
    "ui.committee.member_card",
    "ui.voting.bulletin",
    "ui.voting.monitoring",
    "ui.voting.vote_counting",
    "ui.voting.protocol",
    "ui.voting.extract",
    "ui.voting.ppz_submission",
    "ui.service.access_tables_page",
    "ui.service.db_export",
    "ui.main_window",
    "api_client",
]


@pytest.mark.parametrize("module_name", PAGE_MODULES)
def test_ui_module_imports(module_name: str):
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_nav_items_cover_sidebar_pages():
    keys = set()
    for entry in NAV_ITEMS:
        if entry == "---":
            continue
        _, page_key = entry
        if page_key is not None:
            keys.add(page_key)
    expected = {
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
        "bulletins",
        "monitoring",
        "vote_results",
        "protocols",
        "extracts",
        "ppz_submissions",
        "access_mirror",
        "db_export",
    }
    assert expected <= keys


def test_api_client_has_voting_methods():
    from api_client import APIClient

    for name in (
        "create_bulletin",
        "record_vote",
        "get_vote_results",
        "create_protocol",
        "assign_signing_right",
    ):
        assert hasattr(APIClient, name)
        assert callable(getattr(APIClient, name))


def test_record_vote_docstring_mentions_value():
    from api_client import APIClient

    sig = inspect.signature(APIClient.record_vote)
    assert "question_id" in sig.parameters
