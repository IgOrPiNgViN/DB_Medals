"""Tests for /api/awards endpoints."""

import pytest
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_award(client: TestClient, **overrides) -> dict:
    payload = {
        "name": "Медаль за доблесть",
        "award_type": "medal",
        "description": "Описание медали",
    }
    payload.update(overrides)
    r = client.post("/api/awards/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── Award CRUD ───────────────────────────────────────────────────────────────

class TestAwardCRUD:
    def test_create_medal(self, client):
        data = _create_award(client, name="Золотая медаль", award_type="medal")
        assert data["id"] > 0
        assert data["name"] == "Золотая медаль"
        assert data["award_type"] == "medal"

    def test_create_ppz(self, client):
        data = _create_award(client, name="ППЗ Честь", award_type="ppz")
        assert data["award_type"] == "ppz"

    def test_create_distinction(self, client):
        data = _create_award(client, name="Знак отличия", award_type="distinction")
        assert data["award_type"] == "distinction"

    def test_create_decoration(self, client):
        data = _create_award(client, name="Украшение", award_type="decoration")
        assert data["award_type"] == "decoration"

    def test_list_awards(self, client):
        _create_award(client, name="Медаль А")
        _create_award(client, name="Медаль Б")
        r = client.get("/api/awards/")
        assert r.status_code == 200
        names = [a["name"] for a in r.json()]
        assert "Медаль А" in names
        assert "Медаль Б" in names

    def test_list_awards_filter_by_type(self, client):
        _create_award(client, name="Медаль X", award_type="medal")
        _create_award(client, name="ППЗ X", award_type="ppz")
        r = client.get("/api/awards/", params={"award_type": "medal"})
        assert r.status_code == 200
        types = {a["award_type"] for a in r.json()}
        assert types == {"medal"} or "ppz" not in types

    def test_get_award(self, client):
        award = _create_award(client, name="Проверочная медаль")
        r = client.get(f"/api/awards/{award['id']}")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Проверочная медаль"
        assert body["has_image"] is False
        assert body["has_image_back"] is False
        assert body["has_establishment"] is False
        assert body["has_development"] is False
        assert body["establishment"] is None
        assert body["development"] is None

    def test_get_award_not_found(self, client):
        r = client.get("/api/awards/999999")
        assert r.status_code == 404

    def test_update_award(self, client):
        award = _create_award(client, name="Исходное название")
        r = client.put(
            f"/api/awards/{award['id']}",
            json={"name": "Новое название", "award_type": "medal"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Новое название"

    def test_delete_award(self, client):
        award = _create_award(client, name="Медаль на удаление")
        r = client.delete(f"/api/awards/{award['id']}")
        assert r.status_code == 204
        r2 = client.get(f"/api/awards/{award['id']}")
        assert r2.status_code == 404


# ── Images ───────────────────────────────────────────────────────────────────

FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


class TestAwardImages:
    def test_upload_image_front(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/images",
            files={"image_front": ("test.jpg", FAKE_JPEG, "image/jpeg")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["has_front"] is True

    def test_upload_image_back(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/images",
            files={"image_back": ("back.jpg", FAKE_JPEG, "image/jpeg")},
        )
        assert r.status_code == 200
        assert r.json()["has_back"] is True

    def test_get_image_front(self, client):
        award = _create_award(client)
        client.post(
            f"/api/awards/{award['id']}/images",
            files={"image_front": ("test.jpg", FAKE_JPEG, "image/jpeg")},
        )
        r = client.get(f"/api/awards/{award['id']}/image", params={"side": "front"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/")

    def test_get_image_unwraps_prefix_before_jpeg(self, client):
        """Как в Access OLE: перед JPEG лежит служебный префикс — отдаём чистый JPEG."""
        award = _create_award(client)
        prefix = b"\x00OLE\x01ACCESS" * 8
        wrapped = prefix + FAKE_JPEG
        client.post(
            f"/api/awards/{award['id']}/images",
            files={"image_front": ("w.jpg", wrapped, "application/octet-stream")},
        )
        r = client.get(f"/api/awards/{award['id']}/image", params={"side": "front"})
        assert r.status_code == 200
        assert r.content[:3] == b"\xff\xd8\xff"
        rlist = client.get("/api/awards/")
        assert rlist.status_code == 200
        row = next(x for x in rlist.json() if x["id"] == award["id"])
        assert row["has_image"] is True

    def test_get_image_back_not_found(self, client):
        award = _create_award(client)
        r = client.get(f"/api/awards/{award['id']}/image", params={"side": "back"})
        assert r.status_code == 404

    def test_delete_image_front(self, client):
        award = _create_award(client)
        client.post(
            f"/api/awards/{award['id']}/images",
            files={"image_front": ("test.jpg", FAKE_JPEG, "image/jpeg")},
        )
        r = client.delete(f"/api/awards/{award['id']}/images/front")
        assert r.status_code == 200
        # Confirm gone
        r2 = client.get(f"/api/awards/{award['id']}/image", params={"side": "front"})
        assert r2.status_code == 404

    def test_delete_image_invalid_side(self, client):
        award = _create_award(client)
        r = client.delete(f"/api/awards/{award['id']}/images/invalidside")
        assert r.status_code == 400


# ── Characteristics ───────────────────────────────────────────────────────────

class TestCharacteristics:
    def test_create_characteristic(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/characteristics",
            json={"award_id": award["id"], "field_name": "Материал", "field_value": "Золото"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["field_name"] == "Материал"
        assert data["field_value"] == "Золото"

    def test_list_characteristics(self, client):
        award = _create_award(client)
        client.post(
            f"/api/awards/{award['id']}/characteristics",
            json={"award_id": award["id"], "field_name": "Вес", "field_value": "10г"},
        )
        r = client.get(f"/api/awards/{award['id']}/characteristics")
        assert r.status_code == 200
        assert len(r.json()) >= 1


# ── Establishment ─────────────────────────────────────────────────────────────

class TestEstablishment:
    def test_create_establishment(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/establishment",
            json={
                "award_id": award["id"],
                "establishment_date": "2020-01-15",
                "document_number": "№123",
                "initiator": "Президент",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["document_number"] == "№123"

    def test_get_establishment(self, client):
        award = _create_award(client)
        client.post(
            f"/api/awards/{award['id']}/establishment",
            json={"award_id": award["id"], "document_number": "ДОК-001"},
        )
        r = client.get(f"/api/awards/{award['id']}/establishment")
        assert r.status_code == 200
        assert r.json()["document_number"] == "ДОК-001"

    def test_update_establishment(self, client):
        award = _create_award(client)
        client.post(
            f"/api/awards/{award['id']}/establishment",
            json={"award_id": award["id"], "document_number": "ДОК-001"},
        )
        r = client.put(
            f"/api/awards/{award['id']}/establishment",
            json={"award_id": award["id"], "document_number": "ДОК-002"},
        )
        assert r.status_code == 200
        assert r.json()["document_number"] == "ДОК-002"

    def test_create_establishment_conflict(self, client):
        award = _create_award(client)
        payload = {"award_id": award["id"], "document_number": "ДОК-X"}
        client.post(f"/api/awards/{award['id']}/establishment", json=payload)
        r2 = client.post(f"/api/awards/{award['id']}/establishment", json=payload)
        assert r2.status_code == 409


# ── Development ───────────────────────────────────────────────────────────────

class TestDevelopment:
    def test_create_development(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/development",
            json={
                "award_id": award["id"],
                "developer": "ООО Дизайн",
                "status": "в работе",
                "start_date": "2021-03-01",
            },
        )
        assert r.status_code == 201
        assert r.json()["developer"] == "ООО Дизайн"

    def test_update_development(self, client):
        award = _create_award(client)
        client.post(
            f"/api/awards/{award['id']}/development",
            json={"award_id": award["id"], "developer": "ООО А", "status": "черновик"},
        )
        r = client.put(
            f"/api/awards/{award['id']}/development",
            json={"award_id": award["id"], "developer": "ООО Б", "status": "готово"},
        )
        assert r.status_code == 200
        assert r.json()["developer"] == "ООО Б"
        assert r.json()["status"] == "готово"


# ── Approvals ─────────────────────────────────────────────────────────────────

class TestApprovals:
    def test_create_approval_nk(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/approvals",
            json={
                "award_id": award["id"],
                "approval_type": "nk",
                "approver_name": "НК Комитет",
                "status": "одобрено",
            },
        )
        assert r.status_code == 201
        assert r.json()["approval_type"] == "nk"

    def test_create_approval_heraldists(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/approvals",
            json={"award_id": award["id"], "approval_type": "heraldists"},
        )
        assert r.status_code == 201

    def test_create_approval_relatives(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/approvals",
            json={"award_id": award["id"], "approval_type": "relatives"},
        )
        assert r.status_code == 201

    def test_create_approval_sponsors(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/approvals",
            json={"award_id": award["id"], "approval_type": "sponsors"},
        )
        assert r.status_code == 201

    def test_list_approvals(self, client):
        award = _create_award(client)
        client.post(
            f"/api/awards/{award['id']}/approvals",
            json={"award_id": award["id"], "approval_type": "nk"},
        )
        client.post(
            f"/api/awards/{award['id']}/approvals",
            json={"award_id": award["id"], "approval_type": "heraldists"},
        )
        r = client.get(f"/api/awards/{award['id']}/approvals")
        assert r.status_code == 200
        assert len(r.json()) == 2


# ── Productions ───────────────────────────────────────────────────────────────

class TestProductions:
    def test_create_production(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/productions",
            json={
                "award_id": award["id"],
                "component_type": "medal",
                "supplier": "ОАО Монетный Двор",
                "quantity": 100,
                "unit_price": 500.0,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["component_type"] == "medal"
        assert data["quantity"] == 100

    def test_list_productions(self, client):
        award = _create_award(client)
        client.post(
            f"/api/awards/{award['id']}/productions",
            json={"award_id": award["id"], "component_type": "certificate"},
        )
        r = client.get(f"/api/awards/{award['id']}/productions")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_update_production(self, client):
        award = _create_award(client)
        prod = client.post(
            f"/api/awards/{award['id']}/productions",
            json={"award_id": award["id"], "component_type": "box", "quantity": 10},
        ).json()
        r = client.put(
            f"/api/awards/productions/{prod['id']}",
            json={"quantity": 50, "status": "выполнено"},
        )
        assert r.status_code == 200
        assert r.json()["quantity"] == 50

    def test_delete_production(self, client):
        award = _create_award(client)
        prod = client.post(
            f"/api/awards/{award['id']}/productions",
            json={"award_id": award["id"], "component_type": "badge"},
        ).json()
        r = client.delete(f"/api/awards/productions/{prod['id']}")
        assert r.status_code == 204


# ── Inventory ─────────────────────────────────────────────────────────────────

class TestInventory:
    def test_create_inventory(self, client):
        award = _create_award(client)
        r = client.post(
            f"/api/awards/{award['id']}/inventory",
            json={
                "award_id": award["id"],
                "component_type": "medal",
                "total_count": 10,
                "reserve_count": 3,
                "issued_count": 2,
                "available_count": 0,  # will be computed server-side
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["available_count"] == 5  # 10 - 3 - 2

    def test_update_inventory(self, client):
        award = _create_award(client)
        item = client.post(
            f"/api/awards/{award['id']}/inventory",
            json={
                "award_id": award["id"],
                "component_type": "certificate",
                "total_count": 20,
                "reserve_count": 5,
                "issued_count": 5,
                "available_count": 0,
            },
        ).json()
        r = client.put(
            f"/api/awards/inventory/{item['id']}",
            json={"total_count": 30, "reserve_count": 5, "issued_count": 5},
        )
        assert r.status_code == 200
        assert r.json()["available_count"] == 20

    def test_update_inventory_over_total_400(self, client):
        award = _create_award(client)
        item = client.post(
            f"/api/awards/{award['id']}/inventory",
            json={
                "award_id": award["id"],
                "component_type": "ppz",
                "total_count": 10,
                "reserve_count": 0,
                "issued_count": 0,
                "available_count": 0,
            },
        ).json()
        r = client.put(
            f"/api/awards/inventory/{item['id']}",
            json={"total_count": 5, "reserve_count": 4, "issued_count": 3},
        )
        assert r.status_code == 400


# ── Reports ───────────────────────────────────────────────────────────────────

class TestAwardReports:
    def test_lifecycle_report(self, client):
        r = client.get("/api/awards/lifecycle")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_warehouse_report(self, client):
        r = client.get("/api/awards/warehouse")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_lifecycle_report_has_fields(self, client):
        _create_award(client, name="Отчётная медаль")
        r = client.get("/api/awards/lifecycle")
        assert r.status_code == 200
        items = r.json()
        if items:
            item = items[0]
            assert "id" in item
            assert "name" in item
            assert "status" in item

    def test_warehouse_report_has_fields(self, client):
        award = _create_award(client, name="Складская медаль")
        client.post(
            f"/api/awards/{award['id']}/inventory",
            json={
                "award_id": award["id"],
                "component_type": "medal",
                "total_count": 50,
                "reserve_count": 5,
                "issued_count": 5,
                "available_count": 0,
            },
        )
        r = client.get("/api/awards/warehouse")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        keys = items[0].keys()
        assert "total" in keys or "total_count" in keys
        assert "available" in keys or "available_count" in keys
        assert "low_stock" in keys
