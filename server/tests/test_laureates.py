"""Tests for /api/laureates endpoints."""

import pytest
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_award(client: TestClient, **overrides) -> dict:
    payload = {"name": "Тестовая медаль", "award_type": "medal"}
    payload.update(overrides)
    r = client.post("/api/awards/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _create_laureate(client: TestClient, **overrides) -> dict:
    payload = {
        "full_name": "Иванов Иван Иванович",
        "category": "employee",
        "position": "Главный инженер",
        "organization": "ООО Тест",
    }
    payload.update(overrides)
    r = client.post("/api/laureates/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _link_award(client: TestClient, laureate_id: int, award_id: int, **overrides) -> dict:
    payload = {
        "laureate_id": laureate_id,
        "award_id": award_id,
        "assigned_date": "2024-05-01",
        "initiator": "Директор",
    }
    payload.update(overrides)
    r = client.post(f"/api/laureates/{laureate_id}/awards", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _create_lifecycle(client: TestClient, la_id: int, bulletin_number: str = "Б-001") -> dict:
    payload = {
        "laureate_award_id": la_id,
        "voting_bulletin_number": bulletin_number,
        "nomination_done": False,
    }
    r = client.post(f"/api/laureates/{la_id}/lifecycle", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── Laureate CRUD ─────────────────────────────────────────────────────────────

class TestLaureateCRUD:
    def test_create_employee(self, client):
        data = _create_laureate(client, category="employee")
        assert data["id"] > 0
        assert data["category"] == "employee"

    def test_create_veteran(self, client):
        data = _create_laureate(client, full_name="Ветеран Иван", category="veteran")
        assert data["category"] == "veteran"

    def test_create_university(self, client):
        data = _create_laureate(client, full_name="Универ Иван", category="university")
        assert data["category"] == "university"

    def test_create_nii(self, client):
        data = _create_laureate(client, full_name="НИИ Иван", category="nii")
        assert data["category"] == "nii"

    def test_create_nonprofit(self, client):
        data = _create_laureate(client, full_name="НКО Иван", category="nonprofit")
        assert data["category"] == "nonprofit"

    def test_create_commercial(self, client):
        data = _create_laureate(client, full_name="Коммерц Иван", category="commercial")
        assert data["category"] == "commercial"

    def test_get_laureate(self, client):
        laureate = _create_laureate(client, full_name="Получаемый Лауреат")
        r = client.get(f"/api/laureates/{laureate['id']}")
        assert r.status_code == 200
        assert r.json()["full_name"] == "Получаемый Лауреат"

    def test_get_laureate_not_found(self, client):
        r = client.get("/api/laureates/999999")
        assert r.status_code == 404

    def test_update_laureate(self, client):
        laureate = _create_laureate(client, full_name="Старое Имя")
        r = client.put(
            f"/api/laureates/{laureate['id']}",
            json={"full_name": "Новое Имя"},
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "Новое Имя"

    def test_delete_laureate(self, client):
        laureate = _create_laureate(client, full_name="На удаление")
        r = client.delete(f"/api/laureates/{laureate['id']}")
        assert r.status_code == 204
        assert client.get(f"/api/laureates/{laureate['id']}").status_code == 404

    def test_filter_by_category(self, client):
        _create_laureate(client, full_name="Сотрудник 1", category="employee")
        _create_laureate(client, full_name="Ветеран 1", category="veteran")
        r = client.get("/api/laureates/", params={"category": "employee"})
        assert r.status_code == 200
        categories = {l["category"] for l in r.json()}
        assert "veteran" not in categories


# ── LaureateAward links ───────────────────────────────────────────────────────

class TestLaureateAwardLink:
    def test_link_award(self, client):
        laureate = _create_laureate(client)
        award = _create_award(client)
        la = _link_award(client, laureate["id"], award["id"])
        assert la["id"] > 0
        assert la["award_id"] == award["id"]
        assert la["laureate_id"] == laureate["id"]

    def test_list_laureate_awards(self, client):
        laureate = _create_laureate(client)
        award1 = _create_award(client, name="Награда 1")
        award2 = _create_award(client, name="Награда 2")
        _link_award(client, laureate["id"], award1["id"])
        _link_award(client, laureate["id"], award2["id"])
        r = client.get(f"/api/laureates/{laureate['id']}/awards")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_by_bulletin(self, client):
        """by-bulletin ищет по voting_bulletin_number в lifecycle."""
        laureate = _create_laureate(client)
        award = _create_award(client)
        la = _link_award(client, laureate["id"], award["id"])
        # номер бюллетеня задаётся в lifecycle
        _create_lifecycle(client, la["id"], bulletin_number="Б-777")
        r = client.get(
            "/api/laureates/laureate-awards/by-bulletin",
            params={"bulletin_number": "Б-777"},
        )
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert items[0]["bulletin_number"] == "Б-777"
        assert "full_name" in items[0]

    def test_links_context(self, client):
        laureate = _create_laureate(client)
        award = _create_award(client)
        la = _link_award(client, laureate["id"], award["id"])
        r = client.get(f"/api/laureates/links/{la['id']}")
        assert r.status_code == 200
        data = r.json()
        assert data["laureate_award_id"] == la["id"]
        assert "full_name" in data
        assert "award_name" in data


# ── Lifecycle ─────────────────────────────────────────────────────────────────

class TestLifecycle:
    def _setup(self, client):
        laureate = _create_laureate(client)
        award = _create_award(client)
        la = _link_award(client, laureate["id"], award["id"])
        return la

    def test_create_lifecycle(self, client):
        la = self._setup(client)
        r = client.post(
            f"/api/laureates/{la['id']}/lifecycle",
            json={
                "laureate_award_id": la["id"],
                "nomination_done": False,
                "voting_done": False,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["laureate_award_id"] == la["id"]

    def test_get_lifecycle(self, client):
        la = self._setup(client)
        client.post(
            f"/api/laureates/{la['id']}/lifecycle",
            json={"laureate_award_id": la["id"]},
        )
        r = client.get(f"/api/laureates/{la['id']}/lifecycle")
        assert r.status_code == 200

    def test_update_lifecycle(self, client):
        la = self._setup(client)
        client.post(
            f"/api/laureates/{la['id']}/lifecycle",
            json={"laureate_award_id": la["id"], "nomination_done": False},
        )
        r = client.put(
            f"/api/laureates/{la['id']}/lifecycle",
            json={"nomination_done": True, "voting_done": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["nomination_done"] is True
        assert data["voting_done"] is True

    def test_create_lifecycle_upsert(self, client):
        la = self._setup(client)
        payload = {"laureate_award_id": la["id"], "nomination_done": False}
        r1 = client.post(f"/api/laureates/{la['id']}/lifecycle", json=payload)
        assert r1.status_code == 201
        r2 = client.post(
            f"/api/laureates/{la['id']}/lifecycle",
            json={"laureate_award_id": la["id"], "nomination_done": True},
        )
        assert r2.status_code == 201
        r3 = client.get(f"/api/laureates/{la['id']}/lifecycle")
        assert r3.json()["nomination_done"] is True


# ── Consent file ──────────────────────────────────────────────────────────────

FAKE_PDF = b"%PDF-1.4 test content here"


class TestConsentFile:
    def _setup(self, client):
        laureate = _create_laureate(client)
        award = _create_award(client)
        la = _link_award(client, laureate["id"], award["id"])
        return la

    def test_upload_consent_file(self, client):
        la = self._setup(client)
        r = client.post(
            f"/api/laureates/{la['id']}/consent/file",
            files={"file": ("consent.pdf", FAKE_PDF, "application/pdf")},
        )
        assert r.status_code == 204

    def test_get_consent_file_info(self, client):
        la = self._setup(client)
        client.post(
            f"/api/laureates/{la['id']}/consent/file",
            files={"file": ("consent.pdf", FAKE_PDF, "application/pdf")},
        )
        r = client.get(f"/api/laureates/{la['id']}/consent/file/info")
        assert r.status_code == 200
        data = r.json()
        assert data["exists"] is True
        assert data["filename"] == "consent.pdf"
        assert data["size"] > 0

    def test_get_consent_file_info_not_exists(self, client):
        la = self._setup(client)
        r = client.get(f"/api/laureates/{la['id']}/consent/file/info")
        assert r.status_code == 200
        assert r.json()["exists"] is False

    def test_download_consent_file(self, client):
        la = self._setup(client)
        client.post(
            f"/api/laureates/{la['id']}/consent/file",
            files={"file": ("consent.pdf", FAKE_PDF, "application/pdf")},
        )
        r = client.get(f"/api/laureates/{la['id']}/consent/file")
        assert r.status_code == 200
        assert r.content == FAKE_PDF

    def test_download_consent_file_not_found(self, client):
        la = self._setup(client)
        r = client.get(f"/api/laureates/{la['id']}/consent/file")
        assert r.status_code == 404

    def test_delete_consent_file(self, client):
        la = self._setup(client)
        client.post(
            f"/api/laureates/{la['id']}/consent/file",
            files={"file": ("consent.pdf", FAKE_PDF, "application/pdf")},
        )
        r = client.delete(f"/api/laureates/{la['id']}/consent/file")
        assert r.status_code == 204
        # Confirm gone
        info = client.get(f"/api/laureates/{la['id']}/consent/file/info").json()
        assert info["exists"] is False


# ── Laureate reports ──────────────────────────────────────────────────────────

class TestLaureateReports:
    def test_awards_laureates_report(self, client):
        r = client.get("/api/laureates/reports/awards-laureates")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_incomplete_lifecycle_report(self, client):
        r = client.get("/api/laureates/reports/incomplete-lifecycle")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_statistics_report(self, client):
        r = client.get("/api/laureates/reports/statistics")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_statistics_report_with_date_filter(self, client):
        _create_laureate(client, full_name="Статист 1", category="employee")
        r = client.get(
            "/api/laureates/reports/statistics",
            params={"from_date": "2020-01-01", "to_date": "2026-12-31"},
        )
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        if items:
            assert "category" in items[0]
            assert "count" in items[0]

    def test_awards_laureates_report_structure(self, client):
        laureate = _create_laureate(client)
        award = _create_award(client, name="Наградная медаль")
        _link_award(client, laureate["id"], award["id"])
        r = client.get("/api/laureates/reports/awards-laureates")
        assert r.status_code == 200
        items = r.json()
        award_entry = next((a for a in items if a["award_id"] == award["id"]), None)
        assert award_entry is not None
        assert "award_name" in award_entry
        assert "laureates" in award_entry

    def test_incomplete_lifecycle_shows_missing(self, client):
        laureate = _create_laureate(client)
        award = _create_award(client, name="Незакрытая награда")
        la = _link_award(client, laureate["id"], award["id"])
        # No lifecycle created — should show up as incomplete
        r = client.get("/api/laureates/reports/incomplete-lifecycle")
        assert r.status_code == 200
        items = r.json()
        la_ids = [i["laureate_award_id"] for i in items]
        assert la["id"] in la_ids
