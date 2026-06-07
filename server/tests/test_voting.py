"""Tests for /api/voting endpoints."""

import pytest
from fastapi.testclient import TestClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _create_award(client: TestClient, **overrides) -> dict:
    payload = {"name": "Голосовательная медаль", "award_type": "medal"}
    payload.update(overrides)
    r = client.post("/api/awards/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _create_laureate(client: TestClient, **overrides) -> dict:
    payload = {"full_name": "Голосуемый Лауреат", "category": "employee"}
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


def _create_member(client: TestClient, **overrides) -> dict:
    payload = {"full_name": "Голосующий Член", "is_active": True}
    payload.update(overrides)
    r = client.post("/api/committee/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _create_bulletin(client: TestClient, number: str = "Б-TEST-001", **overrides) -> dict:
    payload = {
        "number": number,
        "bulletin_type": "medal",
        "voting_start": "2024-06-01",
        "voting_end": "2024-06-30",
        "postal_address": "ул. Ленина, 1",
    }
    payload.update(overrides)
    r = client.post("/api/voting/bulletins", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _add_section(client: TestClient, bulletin_id: int, name: str = "Раздел 1") -> dict:
    r = client.post(
        f"/api/voting/bulletins/{bulletin_id}/sections",
        json={"bulletin_id": bulletin_id, "section_name": name, "section_order": 1},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _add_question(
    client: TestClient,
    section_id: int,
    text: str = "Поддержать кандидатуру?",
    la_id: int = None,
) -> dict:
    payload = {
        "section_id": section_id,
        "question_text": text,
        "question_order": 1,
    }
    if la_id is not None:
        payload["laureate_award_id"] = la_id
    r = client.post(f"/api/voting/sections/{section_id}/questions", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _setup_bulletin_with_question(client: TestClient) -> tuple:
    """Returns (bulletin, section, question, member, la)."""
    award = _create_award(client)
    laureate = _create_laureate(client)
    la = _link_award(client, laureate["id"], award["id"])
    member = _create_member(client)
    bulletin = _create_bulletin(client)
    section = _add_section(client, bulletin["id"])
    question = _add_question(client, section["id"], la_id=la["id"])
    return bulletin, section, question, member, la


# ── Bulletin CRUD ─────────────────────────────────────────────────────────────

class TestBulletinCRUD:
    def test_create_bulletin_medal(self, client):
        data = _create_bulletin(client, number="Б-M-001", bulletin_type="medal")
        assert data["id"] > 0
        assert data["bulletin_type"] == "medal"
        assert data["number"] == "Б-M-001"

    def test_create_bulletin_ppz(self, client):
        data = _create_bulletin(client, number="Б-P-001", bulletin_type="ppz")
        assert data["bulletin_type"] == "ppz"

    def test_list_bulletins(self, client):
        _create_bulletin(client, number="Б-LIST-001")
        _create_bulletin(client, number="Б-LIST-002")
        r = client.get("/api/voting/bulletins")
        assert r.status_code == 200
        numbers = [b["number"] for b in r.json()]
        assert "Б-LIST-001" in numbers

    def test_get_bulletin(self, client):
        bulletin = _create_bulletin(client, number="Б-GET-001")
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}")
        assert r.status_code == 200
        assert r.json()["number"] == "Б-GET-001"

    def test_get_bulletin_not_found(self, client):
        r = client.get("/api/voting/bulletins/999999")
        assert r.status_code == 404

    def test_update_bulletin(self, client):
        bulletin = _create_bulletin(client, number="Б-UPD-001")
        r = client.put(
            f"/api/voting/bulletins/{bulletin['id']}",
            json={"postal_address": "ул. Мира, 5", "status": "active"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["postal_address"] == "ул. Мира, 5"
        assert data["status"] == "active"

    def test_delete_bulletin(self, client):
        bulletin = _create_bulletin(client, number="Б-DEL-001")
        r = client.delete(f"/api/voting/bulletins/{bulletin['id']}")
        assert r.status_code == 204
        assert client.get(f"/api/voting/bulletins/{bulletin['id']}").status_code == 404

    def test_get_bulletin_full(self, client):
        bulletin, section, question, _, _ = _setup_bulletin_with_question(client)
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}/full")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == bulletin["id"]
        assert "sections" in data
        assert len(data["sections"]) == 1
        assert len(data["sections"][0]["questions"]) == 1

    def test_bulletin_docx(self, client):
        bulletin, section, question, _, _ = _setup_bulletin_with_question(client)
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}/docx")
        assert r.status_code == 200
        assert "officedocument.wordprocessingml" in r.headers.get("content-type", "")
        assert len(r.content) > 0


# ── Sections & Questions ──────────────────────────────────────────────────────

class TestSectionsQuestions:
    def test_add_section(self, client):
        bulletin = _create_bulletin(client, number="Б-SEC-001")
        r = client.post(
            f"/api/voting/bulletins/{bulletin['id']}/sections",
            json={
                "bulletin_id": bulletin["id"],
                "section_name": "Раздел А",
                "section_order": 1,
            },
        )
        assert r.status_code == 201
        assert r.json()["section_name"] == "Раздел А"

    def test_add_question_with_la(self, client):
        award = _create_award(client)
        laureate = _create_laureate(client)
        la = _link_award(client, laureate["id"], award["id"])
        bulletin = _create_bulletin(client, number="Б-Q-001")
        section = _add_section(client, bulletin["id"])
        r = client.post(
            f"/api/voting/sections/{section['id']}/questions",
            json={
                "section_id": section["id"],
                "question_text": "Поддержать?",
                "laureate_award_id": la["id"],
                "question_order": 1,
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["laureate_award_id"] == la["id"]

    def test_add_question_without_la(self, client):
        bulletin = _create_bulletin(client, number="Б-Q-002")
        section = _add_section(client, bulletin["id"], "Организационные")
        r = client.post(
            f"/api/voting/sections/{section['id']}/questions",
            json={"section_id": section["id"], "question_text": "Утвердить регламент?"},
        )
        assert r.status_code == 201


# ── Distribution ──────────────────────────────────────────────────────────────

class TestDistribution:
    def test_distribute_to_members(self, client):
        bulletin = _create_bulletin(client, number="Б-DIST-001")
        member1 = _create_member(client, full_name="Член Рассылки 1")
        member2 = _create_member(client, full_name="Член Рассылки 2")
        r = client.post(
            f"/api/voting/bulletins/{bulletin['id']}/distribute",
            json={"member_ids": [member1["id"], member2["id"]]},
        )
        assert r.status_code == 201
        dists = r.json()
        assert len(dists) == 2
        for d in dists:
            assert d["sent"] is True

    def test_distribute_nonexistent_member(self, client):
        bulletin = _create_bulletin(client, number="Б-DIST-NOTFOUND")
        r = client.post(
            f"/api/voting/bulletins/{bulletin['id']}/distribute",
            json={"member_ids": [999999]},
        )
        assert r.status_code == 404

    def test_export_distributions_csv(self, client):
        bulletin = _create_bulletin(client, number="Б-CSV-001")
        member = _create_member(client, full_name="CSV Член")
        client.post(
            f"/api/voting/bulletins/{bulletin['id']}/distribute",
            json={"member_ids": [member["id"]]},
        )
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}/distributions.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert b"member_id" in r.content

    def test_list_distributions_with_email(self, client):
        bulletin = _create_bulletin(client, number="Б-LIST-001")
        member = _create_member(client, full_name="List Член", email="list@test.local")
        client.post(
            f"/api/voting/bulletins/{bulletin['id']}/distribute",
            json={"member_ids": [member["id"]]},
        )
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}/distributions")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["member_email"] == "list@test.local"
        assert items[0]["member_name"] == "List Член"

    def test_export_distributions_xlsx(self, client):
        bulletin = _create_bulletin(client, number="Б-XLSX-001")
        member = _create_member(client, full_name="XLSX Член")
        client.post(
            f"/api/voting/bulletins/{bulletin['id']}/distribute",
            json={"member_ids": [member["id"]]},
        )
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}/distributions.xlsx")
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("content-type", "")

    def test_update_distribution(self, client):
        bulletin = _create_bulletin(client, number="Б-DISTUPD-001")
        member = _create_member(client, full_name="Обновляемый Член")
        dists = client.post(
            f"/api/voting/bulletins/{bulletin['id']}/distribute",
            json={"member_ids": [member["id"]]},
        ).json()
        dist_id = dists[0]["id"]
        r = client.put(
            f"/api/voting/distributions/{dist_id}",
            json={"received": True, "received_date": "2024-07-01"},
        )
        assert r.status_code == 200
        assert r.json()["received"] is True

    def test_monitoring(self, client):
        bulletin = _create_bulletin(client, number="Б-MON-001")
        member = _create_member(client, full_name="Мониторинг Член")
        client.post(
            f"/api/voting/bulletins/{bulletin['id']}/distribute",
            json={"member_ids": [member["id"]]},
        )
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}/monitoring")
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert "sent" in items[0]
        assert "member_name" in items[0]


# ── Votes ─────────────────────────────────────────────────────────────────────

class TestVotes:
    def test_record_vote_for(self, client):
        _, _, question, member, _ = _setup_bulletin_with_question(client)
        r = client.post(
            f"/api/voting/questions/{question['id']}/votes",
            json={
                "question_id": question["id"],
                "member_id": member["id"],
                "value": "for",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["value"] == "for"

    def test_record_vote_against(self, client):
        _, _, question, member, _ = _setup_bulletin_with_question(client)
        r = client.post(
            f"/api/voting/questions/{question['id']}/votes",
            json={
                "question_id": question["id"],
                "member_id": member["id"],
                "value": "against",
            },
        )
        assert r.status_code == 201
        assert r.json()["value"] == "against"

    def test_duplicate_vote_409(self, client):
        _, _, question, member, _ = _setup_bulletin_with_question(client)
        vote_payload = {
            "question_id": question["id"],
            "member_id": member["id"],
            "value": "for",
        }
        client.post(f"/api/voting/questions/{question['id']}/votes", json=vote_payload)
        r2 = client.post(f"/api/voting/questions/{question['id']}/votes", json=vote_payload)
        assert r2.status_code == 409

    def test_vote_results(self, client):
        bulletin, section, question, member, _ = _setup_bulletin_with_question(client)
        client.post(
            f"/api/voting/questions/{question['id']}/votes",
            json={"question_id": question["id"], "member_id": member["id"], "value": "for"},
        )
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}/results")
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 1
        res = results[0]
        assert res["question_id"] == question["id"]
        assert res["votes_for"] == 1
        assert res["votes_against"] == 0
        assert res["percent_for"] == 100.0
        assert res["passed"] is True  # 100% >= 65%

    def test_vote_results_failed(self, client):
        """Two against, one for → ~33% → not passed."""
        bulletin, section, question, member1, _ = _setup_bulletin_with_question(client)
        member2 = _create_member(client, full_name="Против 1")
        member3 = _create_member(client, full_name="Против 2")
        client.post(
            f"/api/voting/questions/{question['id']}/votes",
            json={"question_id": question["id"], "member_id": member1["id"], "value": "for"},
        )
        client.post(
            f"/api/voting/questions/{question['id']}/votes",
            json={"question_id": question["id"], "member_id": member2["id"], "value": "against"},
        )
        client.post(
            f"/api/voting/questions/{question['id']}/votes",
            json={"question_id": question["id"], "member_id": member3["id"], "value": "against"},
        )
        r = client.get(f"/api/voting/bulletins/{bulletin['id']}/results")
        assert r.status_code == 200
        res = r.json()[0]
        assert res["passed"] is False


# ── Protocol ──────────────────────────────────────────────────────────────────

class TestProtocol:
    def test_create_protocol(self, client):
        bulletin = _create_bulletin(client, number="Б-PROTO-001")
        r = client.post(
            f"/api/voting/bulletins/{bulletin['id']}/protocol",
            json={
                "bulletin_id": bulletin["id"],
                "number": "П-001",
                "date": "2024-07-15",
                "status": "draft",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["number"] == "П-001"
        assert data["bulletin_id"] == bulletin["id"]

    def test_create_protocol_conflict(self, client):
        bulletin = _create_bulletin(client, number="Б-PROTO-CONF")
        payload = {"bulletin_id": bulletin["id"], "number": "П-CONF", "date": "2024-07-15"}
        client.post(f"/api/voting/bulletins/{bulletin['id']}/protocol", json=payload)
        r2 = client.post(f"/api/voting/bulletins/{bulletin['id']}/protocol", json=payload)
        assert r2.status_code == 409

    def test_list_protocols(self, client):
        bulletin = _create_bulletin(client, number="Б-PROTO-LIST")
        client.post(
            f"/api/voting/bulletins/{bulletin['id']}/protocol",
            json={"bulletin_id": bulletin["id"], "number": "П-LIST-001"},
        )
        r = client.get("/api/voting/protocols")
        assert r.status_code == 200
        numbers = [p["number"] for p in r.json()]
        assert "П-LIST-001" in numbers

    def test_update_protocol(self, client):
        bulletin = _create_bulletin(client, number="Б-PROTO-UPD")
        proto = client.post(
            f"/api/voting/bulletins/{bulletin['id']}/protocol",
            json={"bulletin_id": bulletin["id"], "number": "П-UPD", "status": "draft"},
        ).json()
        r = client.put(
            f"/api/voting/protocols/{proto['id']}",
            json={"status": "signed", "details": "Подписан директором"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "signed"

    def test_protocol_docx(self, client):
        bulletin, section, question, member, _ = _setup_bulletin_with_question(client)
        client.post(
            f"/api/voting/questions/{question['id']}/votes",
            json={"question_id": question["id"], "member_id": member["id"], "value": "for"},
        )
        proto = client.post(
            f"/api/voting/bulletins/{bulletin['id']}/protocol",
            json={"bulletin_id": bulletin["id"], "number": "П-DOCX"},
        ).json()
        r = client.get(f"/api/voting/protocols/{proto['id']}/docx")
        assert r.status_code == 200
        assert "officedocument.wordprocessingml" in r.headers.get("content-type", "")
        assert len(r.content) > 0


# ── Protocol Extracts ─────────────────────────────────────────────────────────

class TestProtocolExtracts:
    def _make_protocol(self, client, number_suffix: str):
        bulletin = _create_bulletin(client, number=f"Б-EXT-{number_suffix}")
        proto = client.post(
            f"/api/voting/bulletins/{bulletin['id']}/protocol",
            json={"bulletin_id": bulletin["id"], "number": f"П-EXT-{number_suffix}"},
        ).json()
        return proto

    def test_create_extract(self, client):
        award = _create_award(client)
        laureate = _create_laureate(client)
        la = _link_award(client, laureate["id"], award["id"])
        proto = self._make_protocol(client, "CREATE")
        r = client.post(
            f"/api/voting/protocols/{proto['id']}/extracts",
            json={
                "protocol_id": proto["id"],
                "laureate_award_id": la["id"],
                "extract_date": "2024-08-01",
                "details": "Выписка о награждении",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["protocol_id"] == proto["id"]
        assert data["laureate_award_id"] == la["id"]

    def test_list_extracts(self, client):
        award = _create_award(client)
        laureate = _create_laureate(client)
        la = _link_award(client, laureate["id"], award["id"])
        proto = self._make_protocol(client, "LIST")
        client.post(
            f"/api/voting/protocols/{proto['id']}/extracts",
            json={"protocol_id": proto["id"], "laureate_award_id": la["id"]},
        )
        r = client.get("/api/voting/extracts")
        assert r.status_code == 200
        ids = [e["protocol_id"] for e in r.json()]
        assert proto["id"] in ids

    def test_extract_docx(self, client):
        award = _create_award(client)
        laureate = _create_laureate(client)
        la = _link_award(client, laureate["id"], award["id"])
        proto = self._make_protocol(client, "DOCX")
        extract = client.post(
            f"/api/voting/protocols/{proto['id']}/extracts",
            json={"protocol_id": proto["id"], "laureate_award_id": la["id"]},
        ).json()
        r = client.get(f"/api/voting/extracts/{extract['id']}/docx")
        assert r.status_code == 200
        assert "officedocument.wordprocessingml" in r.headers.get("content-type", "")
        assert len(r.content) > 0


# ── PPZ Submissions ───────────────────────────────────────────────────────────

class TestPPZSubmissions:
    def _setup(self, client):
        award = _create_award(client)
        laureate = _create_laureate(client)
        la = _link_award(client, laureate["id"], award["id"])
        member = _create_member(client, full_name="Уполномоченный")
        return la, member

    def test_create_ppz_submission(self, client):
        la, member = self._setup(client)
        r = client.post(
            "/api/voting/ppz-submissions",
            json={
                "laureate_award_id": la["id"],
                "authorized_member_id": member["id"],
                "submission_number": "ППЗ-001",
                "date": "2024-09-01",
                "details": "Детали представления",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["submission_number"] == "ППЗ-001"
        assert data["laureate_award_id"] == la["id"]

    def test_list_ppz_submissions(self, client):
        la, member = self._setup(client)
        client.post(
            "/api/voting/ppz-submissions",
            json={
                "laureate_award_id": la["id"],
                "authorized_member_id": member["id"],
                "submission_number": "ППЗ-LIST-001",
            },
        )
        r = client.get("/api/voting/ppz-submissions")
        assert r.status_code == 200
        numbers = [p["submission_number"] for p in r.json()]
        assert "ППЗ-LIST-001" in numbers

    def test_ppz_submission_docx(self, client):
        la, member = self._setup(client)
        subm = client.post(
            "/api/voting/ppz-submissions",
            json={
                "laureate_award_id": la["id"],
                "authorized_member_id": member["id"],
                "submission_number": "ППЗ-DOCX",
            },
        ).json()
        r = client.get(f"/api/voting/ppz-submissions/{subm['id']}/docx")
        assert r.status_code == 200
        assert "officedocument.wordprocessingml" in r.headers.get("content-type", "")
        assert len(r.content) > 0
