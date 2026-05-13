"""Tests for /api/committee endpoints."""

import pytest
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_award(client: TestClient, **overrides) -> dict:
    payload = {"name": "Комитетная медаль", "award_type": "medal"}
    payload.update(overrides)
    r = client.post("/api/awards/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _create_member(client: TestClient, **overrides) -> dict:
    payload = {
        "full_name": "Петров Пётр Петрович",
        "position": "Председатель",
        "organization": "НК ООН ПКР",
        "is_active": True,
    }
    payload.update(overrides)
    r = client.post("/api/committee/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── CommitteeMember CRUD ─────────────────────────────────────────────────────

class TestCommitteeMemberCRUD:
    def test_create_member(self, client):
        data = _create_member(client)
        assert data["id"] > 0
        assert data["full_name"] == "Петров Пётр Петрович"
        assert data["is_active"] is True

    def test_get_member(self, client):
        member = _create_member(client, full_name="Сидоров Сидор")
        r = client.get(f"/api/committee/{member['id']}")
        assert r.status_code == 200
        assert r.json()["full_name"] == "Сидоров Сидор"

    def test_get_member_not_found(self, client):
        r = client.get("/api/committee/999999")
        assert r.status_code == 404

    def test_list_members(self, client):
        _create_member(client, full_name="Член А")
        _create_member(client, full_name="Член Б")
        r = client.get("/api/committee/")
        assert r.status_code == 200
        names = [m["full_name"] for m in r.json()]
        assert "Член А" in names
        assert "Член Б" in names

    def test_filter_active_members(self, client):
        _create_member(client, full_name="Активный", is_active=True)
        _create_member(client, full_name="Неактивный", is_active=False)
        r = client.get("/api/committee/", params={"is_active": True})
        assert r.status_code == 200
        for m in r.json():
            assert m["is_active"] is True

    def test_filter_inactive_members(self, client):
        _create_member(client, full_name="Активный 2", is_active=True)
        _create_member(client, full_name="Неактивный 2", is_active=False)
        r = client.get("/api/committee/", params={"is_active": False})
        assert r.status_code == 200
        for m in r.json():
            assert m["is_active"] is False

    def test_update_member(self, client):
        member = _create_member(client, full_name="Старое ФИО")
        r = client.put(
            f"/api/committee/{member['id']}",
            json={"full_name": "Новое ФИО", "position": "Зам. председателя"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["full_name"] == "Новое ФИО"
        assert data["position"] == "Зам. председателя"

    def test_deactivate_member(self, client):
        member = _create_member(client, is_active=True)
        r = client.put(f"/api/committee/{member['id']}", json={"is_active": False})
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_delete_member(self, client):
        member = _create_member(client, full_name="На удаление")
        r = client.delete(f"/api/committee/{member['id']}")
        assert r.status_code == 204
        assert client.get(f"/api/committee/{member['id']}").status_code == 404

    def test_member_has_all_fields(self, client):
        member = _create_member(
            client,
            full_name="Полный Состав",
            position="Секретарь",
            organization="Организация X",
            phone="+7-900-000-00-00",
            email="test@example.com",
            notes="Примечание",
        )
        r = client.get(f"/api/committee/{member['id']}")
        assert r.status_code == 200
        data = r.json()
        assert data["phone"] == "+7-900-000-00-00"
        assert data["email"] == "test@example.com"
        assert data["notes"] == "Примечание"


# ── Signing Rights ────────────────────────────────────────────────────────────

class TestSigningRights:
    def test_assign_signing_right_signer(self, client):
        member = _create_member(client)
        award = _create_award(client)
        r = client.post(
            f"/api/committee/{member['id']}/signing-rights",
            json={
                "member_id": member["id"],
                "award_id": award["id"],
                "role": "signer",
                "assigned_date": "2024-01-10",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["role"] == "signer"
        assert data["award_id"] == award["id"]

    def test_assign_signing_right_authorized(self, client):
        member = _create_member(client)
        award = _create_award(client)
        r = client.post(
            f"/api/committee/{member['id']}/signing-rights",
            json={
                "member_id": member["id"],
                "award_id": award["id"],
                "role": "authorized",
            },
        )
        assert r.status_code == 201
        assert r.json()["role"] == "authorized"

    def test_list_signing_rights(self, client):
        member = _create_member(client)
        award1 = _create_award(client, name="Право 1")
        award2 = _create_award(client, name="Право 2")
        client.post(
            f"/api/committee/{member['id']}/signing-rights",
            json={"member_id": member["id"], "award_id": award1["id"], "role": "signer"},
        )
        client.post(
            f"/api/committee/{member['id']}/signing-rights",
            json={"member_id": member["id"], "award_id": award2["id"], "role": "authorized"},
        )
        r = client.get(f"/api/committee/{member['id']}/signing-rights")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_delete_signing_right(self, client):
        member = _create_member(client)
        award = _create_award(client)
        right = client.post(
            f"/api/committee/{member['id']}/signing-rights",
            json={"member_id": member["id"], "award_id": award["id"], "role": "signer"},
        ).json()
        r = client.delete(f"/api/committee/signing-rights/{right['id']}")
        assert r.status_code == 204
        # Confirm gone from list
        rights_r = client.get(f"/api/committee/{member['id']}/signing-rights")
        ids = [sr["id"] for sr in rights_r.json()]
        assert right["id"] not in ids

    def test_delete_nonexistent_signing_right(self, client):
        r = client.delete("/api/committee/signing-rights/999999")
        assert r.status_code == 404
