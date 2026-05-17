"""Pytest: клиентский UI без реального API."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

CLIENT_ROOT = Path(__file__).resolve().parents[1]
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))


@pytest.fixture(scope="session")
def qapp():
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_api():
    """API-заглушка: все GET возвращают пустые списки/словари."""
    api = MagicMock()
    api.health_check.return_value = {"status": "ok"}
    api.get_awards.return_value = []
    api.get_award.return_value = {"id": 1, "name": "Test", "award_type": "medal"}
    api.get_characteristics.return_value = []
    api.get_establishment.return_value = {}
    api.get_development.return_value = {}
    api.get_approvals.return_value = []
    api.get_productions.return_value = []
    api.get_inventory.return_value = []
    api.get_award_lifecycle_report.return_value = []
    api.get_warehouse_report.return_value = []
    api.get_laureates.return_value = []
    api.get_laureate.return_value = {"id": 1, "full_name": "Test"}
    api.get_laureate_awards.return_value = []
    api.get_laureate_lifecycle.return_value = {}
    api.get_laureate_awards_by_bulletin_number.return_value = []
    api.report_awards_laureates.return_value = []
    api.report_incomplete_lifecycle.return_value = []
    api.report_lifecycle_by_stage.return_value = {"counts": {}, "by_stage": []}
    api.report_statistics.return_value = {}
    api.get_awards_laureates_report_v1.return_value = []
    api.get_incomplete_lifecycle_report_v1.return_value = []
    api.get_statistics_report_v1.return_value = []
    api.get_committee_members.return_value = []
    api.get_committee_member.return_value = {"id": 1, "full_name": "Test", "is_active": True}
    api.get_signing_rights.return_value = []
    api.get_bulletins.return_value = []
    api.get_bulletin_full.return_value = {"sections": []}
    api.get_bulletin_monitoring.return_value = []
    api.get_vote_results.return_value = []
    api.get_protocols.return_value = []
    api.list_protocol_extracts.return_value = []
    api.list_ppz_submissions.return_value = []
    api.list_access_mirror_tables.return_value = []
    api.get_access_mirror_data.side_effect = Exception("404")
    return api
