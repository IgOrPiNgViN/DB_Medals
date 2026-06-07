"""Tests for /api/reports endpoints."""

import pytest
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_award(client: TestClient, **overrides) -> dict:
    payload = {"name": "Отчётная медаль", "award_type": "medal"}
    payload.update(overrides)
    r = client.post("/api/awards/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _create_laureate(client: TestClient, **overrides) -> dict:
    payload = {"full_name": "Отчётный Лауреат", "category": "employee"}
    payload.update(overrides)
    r = client.post("/api/laureates/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _link_award(client: TestClient, laureate_id: int, award_id: int) -> dict:
    payload = {
        "laureate_id": laureate_id,
        "award_id": award_id,
        "assigned_date": "2024-05-01",
    }
    r = client.post(f"/api/laureates/{laureate_id}/awards", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _add_inventory(client: TestClient, award_id: int, **overrides) -> dict:
    payload = {
        "award_id": award_id,
        "component_type": "medal",
        "total_count": 50,
        "reserve_count": 5,
        "issued_count": 5,
        "available_count": 0,
    }
    payload.update(overrides)
    r = client.post(f"/api/awards/{award_id}/inventory", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── Basic availability tests ──────────────────────────────────────────────────

class TestReportsAvailability:
    def test_award_lifecycle(self, client):
        r = client.get("/api/reports/award-lifecycle")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_warehouse_summary(self, client):
        r = client.get("/api/reports/warehouse-summary")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_awards_laureates(self, client):
        r = client.get("/api/reports/awards-laureates")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_incomplete_lifecycle(self, client):
        r = client.get("/api/reports/incomplete-lifecycle")
        assert r.status_code == 200

    def test_incomplete_lifecycle_sections(self, client):
        r = client.get("/api/reports/incomplete-lifecycle-sections")
        assert r.status_code == 200
        body = r.json()
        assert "sections" in body
        assert "for_voting" in body["sections"]
        assert "for_publication" in body["sections"]
        assert "counts" in body

    def test_lifecycle_by_stage(self, client):
        r = client.get("/api/reports/lifecycle-by-stage")
        assert r.status_code == 200
        data = r.json()
        assert "counts" in data
        assert "by_stage" in data

    def test_statistics(self, client):
        r = client.get("/api/reports/statistics")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "by_category" in data

    def test_statistics_with_dates(self, client):
        r = client.get(
            "/api/reports/statistics",
            params={"from_date": "2020-01-01", "to_date": "2026-12-31"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert "by_category" in data

    def test_site_export(self, client):
        r = client.get("/api/reports/site-export")
        assert r.status_code == 200
        data = r.json()
        assert "generated_at" in data
        assert "count" in data
        assert "items" in data


# ── Structural / content tests ────────────────────────────────────────────────

class TestReportsContent:
    def test_lifecycle_by_stage_structure(self, client):
        """counts dict and by_stage dict must share the same keys."""
        r = client.get("/api/reports/lifecycle-by-stage")
        assert r.status_code == 200
        data = r.json()
        counts = data["counts"]
        by_stage = data["by_stage"]
        # All expected stages must be present
        for stage in ("nomination", "voting", "decision", "registration", "ceremony", "publication", "complete"):
            assert stage in counts, f"Missing stage key in counts: {stage}"
            assert stage in by_stage, f"Missing stage key in by_stage: {stage}"
        # Each by_stage value must be a list
        for stage, entries in by_stage.items():
            assert isinstance(entries, list), f"by_stage['{stage}'] should be a list"

    def test_statistics_total_matches_sum(self, client):
        """total should equal sum of all by_category counts."""
        _create_laureate(client, full_name="Статист А", category="employee")
        _create_laureate(client, full_name="Статист Б", category="veteran")
        r = client.get("/api/reports/statistics")
        data = r.json()
        total = data["total"]
        calculated = sum(c["count"] for c in data["by_category"])
        assert total == calculated

    def test_statistics_by_category_has_percent(self, client):
        _create_laureate(client, full_name="Статист В", category="commercial")
        r = client.get("/api/reports/statistics")
        data = r.json()
        for item in data["by_category"]:
            assert "category" in item
            assert "count" in item
            assert "percent" in item
            assert 0.0 <= item["percent"] <= 100.0

    def test_award_lifecycle_has_fields(self, client):
        _create_award(client, name="Жизненный Цикл Медаль")
        r = client.get("/api/reports/award-lifecycle")
        items = r.json()
        assert len(items) >= 1
        item = items[0]
        assert "id" in item
        assert "name" in item
        assert "award_type" in item
        assert "approvals_count" in item
        assert "productions_count" in item

    def test_warehouse_summary_has_fields(self, client):
        award = _create_award(client, name="Складской Отчёт")
        _add_inventory(client, award["id"])
        r = client.get("/api/reports/warehouse-summary")
        items = r.json()
        assert len(items) >= 1
        item = items[0]
        assert "award_name" in item
        assert "component_type" in item
        assert "total_count" in item
        assert "available_count" in item
        assert "low_stock" in item

    def test_awards_laureates_grouped_by_award(self, client):
        award = _create_award(client, name="Группированная Медаль")
        laureate1 = _create_laureate(client, full_name="Лауреат ГМ 1")
        laureate2 = _create_laureate(client, full_name="Лауреат ГМ 2")
        _link_award(client, laureate1["id"], award["id"])
        _link_award(client, laureate2["id"], award["id"])
        r = client.get("/api/reports/awards-laureates")
        assert r.status_code == 200
        items = r.json()
        award_entry = next((a for a in items if a["award_id"] == award["id"]), None)
        assert award_entry is not None
        assert award_entry["laureates_count"] == 2
        assert len(award_entry["laureates"]) == 2

    def test_incomplete_lifecycle_includes_no_lifecycle(self, client):
        award = _create_award(client, name="Незавершённая Медаль")
        laureate = _create_laureate(client, full_name="Незавершённый Лауреат")
        la = _link_award(client, laureate["id"], award["id"])
        r = client.get("/api/reports/incomplete-lifecycle")
        assert r.status_code == 200
        la_ids = [item["laureate_award_id"] for item in r.json()]
        assert la["id"] in la_ids

    def test_site_export_count_matches_items(self, client):
        award = _create_award(client, name="Сайт Медаль")
        laureate = _create_laureate(client, full_name="Сайт Лауреат")
        _link_award(client, laureate["id"], award["id"])
        r = client.get("/api/reports/site-export")
        data = r.json()
        assert data["count"] == len(data["items"])

    def test_site_export_items_have_fields(self, client):
        award = _create_award(client, name="Сайт Поля Медаль")
        laureate = _create_laureate(client, full_name="Сайт Поля Лауреат")
        la = _link_award(client, laureate["id"], award["id"])
        r = client.get("/api/reports/site-export")
        data = r.json()
        la_entry = next(
            (i for i in data["items"] if i["laureate_award_id"] == la["id"]), None
        )
        assert la_entry is not None
        assert la_entry["laureate_name"] == "Сайт Поля Лауреат"
        assert la_entry["award_name"] == "Сайт Поля Медаль"
        assert "award_type" in la_entry
        assert "laureate_category" in la_entry

    def test_warehouse_grouped(self, client):
        r = client.get("/api/reports/warehouse-summary-grouped", params={"award_type": "medal"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_statistics_groups(self, client):
        r = client.get("/api/reports/statistics")
        assert r.status_code == 200
        data = r.json()
        assert "groups" in data
        assert "total" in data

    def test_warehouse_low_stock_flag(self, client):
        award = _create_award(client, name="Малый Склад")
        _add_inventory(
            client,
            award["id"],
            total_count=5,
            reserve_count=0,
            issued_count=0,
            available_count=0,
        )
        r = client.get("/api/reports/warehouse-summary")
        items = r.json()
        award_items = [i for i in items if i["award_id"] == award["id"]]
        assert len(award_items) >= 1
        # available < 10 → low_stock = True
        assert award_items[0]["low_stock"] is True

    def test_approvals_monitor(self, client):
        award = _create_award(client, name="Монитор Соглас")
        client.post(
            f"/api/awards/{award['id']}/approvals",
            json={"award_id": award["id"], "approval_type": "nk", "status": "ожидание"},
        )
        r = client.get("/api/reports/approvals-monitor")
        assert r.status_code == 200
        items = r.json()
        assert any(i["award_id"] == award["id"] for i in items)

    def test_awards_by_bulletin(self, client):
        award = _create_award(client, name="Бюллетень Медаль")
        laureate = _create_laureate(client, full_name="Бюллетень Лауреат")
        la = _link_award(client, laureate["id"], award["id"])
        client.put(
            f"/api/laureates/{la['id']}/lifecycle",
            json={"voting_bulletin_number": "B-TEST-42"},
        )
        r = client.get("/api/reports/awards-by-bulletin")
        assert r.status_code == 200
        data = r.json()
        assert data["total_links"] >= 1
        assert any(g["bulletin_number"] == "B-TEST-42" for g in data["groups"])

    def test_warehouse_reservations_postponed(self, client):
        award = _create_award(client, name="Отложенная Медаль")
        laureate = _create_laureate(client, full_name="Отложенный Лауреат")
        la = _link_award(client, laureate["id"], award["id"])
        client.put(
            f"/api/laureates/{la['id']}/lifecycle",
            json={"registration_pending_issue": True},
        )
        r = client.get("/api/reports/warehouse-reservations")
        assert r.status_code == 200
        data = r.json()
        assert "postponed_pending" in data
        ids = [x["laureate_award_id"] for x in data["postponed_pending"]]
        assert la["id"] in ids
