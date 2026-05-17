"""
Сквозной сценарий: все основные операции, которые выполняет десктоп-клиент.
Проверяет ожидаемые коды ответа (200/201/204) и корректные тела запросов UI.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _assert_ok(r, allowed=(200, 201, 204)):
    assert r.status_code in allowed, f"{r.request.method} {r.url} -> {r.status_code}: {r.text[:500]}"


class TestFullClientWorkflow:
    """Один связный прогон «как пользователь в UI»."""

    def test_end_to_end(self, client: TestClient):
        # ── Health / root ───────────────────────────────────────────────
        _assert_ok(client.get("/api/health"))
        _assert_ok(client.get("/api/"))
        _assert_ok(client.get("/"))

        # ── Awards ──────────────────────────────────────────────────────
        r = client.post(
            "/api/awards/",
            json={
                "name": "QA Медаль полный цикл",
                "award_type": "medal",
                "description": "smoke",
            },
        )
        _assert_ok(r, (201,))
        award = r.json()
        aid = award["id"]

        _assert_ok(client.get("/api/awards/"))
        _assert_ok(client.get(f"/api/awards/{aid}"))
        _assert_ok(
            client.put(f"/api/awards/{aid}", json={"name": "QA Медаль (обновлена)", "award_type": "medal"}),
        )

        _assert_ok(
            client.post(
                f"/api/awards/{aid}/characteristics",
                json={"award_id": aid, "field_name": "Материал", "field_value": "Золото"},
            ),
            (201,),
        )
        _assert_ok(client.get(f"/api/awards/{aid}/characteristics"))

        _assert_ok(
            client.post(
                f"/api/awards/{aid}/establishment",
                json={"award_id": aid, "document_number": "QA-EST-1"},
            ),
            (201,),
        )
        _assert_ok(client.get(f"/api/awards/{aid}/establishment"))
        _assert_ok(
            client.put(
                f"/api/awards/{aid}/establishment",
                json={"award_id": aid, "document_number": "QA-EST-2"},
            ),
        )

        _assert_ok(
            client.post(
                f"/api/awards/{aid}/development",
                json={"award_id": aid, "developer": "QA Dev", "status": "готово"},
            ),
            (201,),
        )
        _assert_ok(client.get(f"/api/awards/{aid}/development"))

        _assert_ok(
            client.post(
                f"/api/awards/{aid}/approvals",
                json={
                    "award_id": aid,
                    "approval_type": "nk",
                    "approver_name": "НК",
                    "status": "одобрено",
                },
            ),
            (201,),
        )
        _assert_ok(client.get(f"/api/awards/{aid}/approvals"))

        prod = client.post(
            f"/api/awards/{aid}/productions",
            json={
                "award_id": aid,
                "component_type": "medal",
                "supplier": "QA Plant",
                "quantity": 10,
                "order_date": "2024-01-01",
            },
        )
        _assert_ok(prod, (201,))
        pid = prod.json()["id"]
        _assert_ok(client.get(f"/api/awards/{aid}/productions"))
        _assert_ok(
            client.put(
                f"/api/awards/productions/{pid}",
                json={"quantity": 12, "supplier": "QA Plant Updated"},
            ),
        )

        inv = client.post(
            f"/api/awards/{aid}/inventory",
            json={
                "award_id": aid,
                "component_type": "medal",
                "total_count": 20,
                "reserve_count": 2,
                "issued_count": 3,
                "available_count": 15,
            },
        )
        _assert_ok(inv, (201,))
        iid = inv.json()["id"]
        _assert_ok(client.get(f"/api/awards/{aid}/inventory"))
        _assert_ok(
            client.put(
                f"/api/awards/inventory/{iid}",
                json={"award_id": aid, "total_count": 25, "available_count": 20},
            ),
        )

        _assert_ok(
            client.post(
                f"/api/awards/{aid}/images",
                files={"image_front": ("q.jpg", FAKE_JPEG, "image/jpeg")},
            ),
        )
        _assert_ok(client.get(f"/api/awards/{aid}/image", params={"side": "front"}))
        _assert_ok(client.delete(f"/api/awards/{aid}/images/front"), (200, 204))

        _assert_ok(client.get("/api/awards/lifecycle"))
        _assert_ok(client.get("/api/awards/warehouse"))

        # ── Laureates ───────────────────────────────────────────────────
        lr = client.post(
            "/api/laureates/",
            json={"full_name": "QA Лауреат Сквозной", "category": "employee"},
        )
        _assert_ok(lr, (201,))
        lid = lr.json()["id"]
        _assert_ok(client.get("/api/laureates/"))
        _assert_ok(client.get(f"/api/laureates/{lid}"))

        la = client.post(
            f"/api/laureates/{lid}/awards",
            json={
                "laureate_id": lid,
                "award_id": aid,
                "assigned_date": "2024-06-01",
            },
        )
        _assert_ok(la, (201,))
        la_id = la.json()["id"]
        _assert_ok(client.get(f"/api/laureates/{lid}/awards"))
        _assert_ok(client.get(f"/api/laureates/links/{la_id}"))

        _assert_ok(
            client.post(
                f"/api/laureates/{la_id}/lifecycle",
                json={
                    "laureate_award_id": la_id,
                    "voting_bulletin_number": "QA-BUL-99",
                    "nomination_done": True,
                },
            ),
            (201,),
        )
        _assert_ok(client.get(f"/api/laureates/{la_id}/lifecycle"))
        _assert_ok(
            client.put(
                f"/api/laureates/{la_id}/lifecycle",
                json={"laureate_award_id": la_id, "voting_done": True},
            ),
        )

        _assert_ok(
            client.get(
                "/api/laureates/laureate-awards/by-bulletin",
                params={"bulletin_number": "QA-BUL-99"},
            ),
        )
        _assert_ok(client.get(f"/api/laureates/{la_id}/consent/file/info"))

        gen = client.get(f"/api/laureates/{la_id}/consent/generate")
        if gen.status_code == 500 and "template" in gen.text.lower():
            pytest.skip("consent template file not available in test env")
        _assert_ok(gen)

        _assert_ok(client.get("/api/laureates/reports/awards-laureates"))
        _assert_ok(client.get("/api/laureates/reports/incomplete-lifecycle"))
        _assert_ok(client.get("/api/laureates/reports/statistics"))

        # ── Committee ───────────────────────────────────────────────────
        mem = client.post(
            "/api/committee/",
            json={"full_name": "QA Член НК", "is_active": True},
        )
        _assert_ok(mem, (201,))
        mid = mem.json()["id"]
        _assert_ok(client.get("/api/committee/"))
        _assert_ok(client.get(f"/api/committee/{mid}"))

        sr = client.post(
            f"/api/committee/{mid}/signing-rights",
            json={"member_id": mid, "award_id": aid, "role": "signer"},
        )
        _assert_ok(sr, (201,))
        right_id = sr.json()["id"]
        _assert_ok(client.get(f"/api/committee/{mid}/signing-rights"))

        # ── Voting (payloads как в UI) ──────────────────────────────────
        bul = client.post(
            "/api/voting/bulletins",
            json={
                "number": "QA-BUL-99",
                "bulletin_type": "medal",
                "voting_start": "2026-05-01",
                "voting_end": "2026-05-31",
                "postal_address": None,
            },
        )
        _assert_ok(bul, (201,))
        bid = bul.json()["id"]
        _assert_ok(client.get("/api/voting/bulletins"))
        _assert_ok(client.get(f"/api/voting/bulletins/{bid}"))
        _assert_ok(client.get(f"/api/voting/bulletins/{bid}/full"))

        sec = client.post(
            f"/api/voting/bulletins/{bid}/sections",
            json={
                "bulletin_id": bid,
                "section_name": "Учреждение наград и НК",
                "section_order": 0,
            },
        )
        _assert_ok(sec, (201,))
        sid = sec.json()["id"]

        q = client.post(
            f"/api/voting/sections/{sid}/questions",
            json={
                "section_id": sid,
                "question_text": "QA: поддержать?",
                "question_order": 0,
            },
        )
        _assert_ok(q, (201,))
        qid = q.json()["id"]

        dist = client.post(
            f"/api/voting/bulletins/{bid}/distribute",
            json={"member_ids": [mid]},
        )
        _assert_ok(dist, (201,))
        dist_id = dist.json()[0]["id"]

        _assert_ok(
            client.put(
                f"/api/voting/distributions/{dist_id}",
                json={"received": True, "received_date": "2026-05-10"},
            ),
        )
        _assert_ok(client.get(f"/api/voting/bulletins/{bid}/monitoring"))
        _assert_ok(client.get(f"/api/voting/bulletins/{bid}/distributions.csv"))
        _assert_ok(client.get(f"/api/voting/bulletins/{bid}/distributions.xlsx"))

        vote = client.post(
            f"/api/voting/questions/{qid}/votes",
            json={
                "question_id": qid,
                "member_id": mid,
                "value": "for",
            },
        )
        _assert_ok(vote, (201,))

        _assert_ok(client.get(f"/api/voting/bulletins/{bid}/results"))
        _assert_ok(client.get(f"/api/voting/bulletins/{bid}/docx"))

        proto = client.post(
            f"/api/voting/bulletins/{bid}/protocol",
            json={
                "bulletin_id": bid,
                "number": "П-QA-99",
                "date": "2026-05-15",
            },
        )
        _assert_ok(proto, (201,))
        proto_id = proto.json()["id"]
        _assert_ok(client.get("/api/voting/protocols"))
        _assert_ok(
            client.put(f"/api/voting/protocols/{proto_id}", json={"status": "signed"}),
        )
        _assert_ok(client.get(f"/api/voting/protocols/{proto_id}/docx"))

        ext = client.post(
            f"/api/voting/protocols/{proto_id}/extracts",
            json={"protocol_id": proto_id, "laureate_award_id": la_id},
        )
        _assert_ok(ext, (201,))
        ext_id = ext.json()["id"]
        _assert_ok(client.get("/api/voting/extracts"))
        _assert_ok(client.get(f"/api/voting/extracts/{ext_id}/docx"))

        ppz = client.post(
            "/api/voting/ppz-submissions",
            json={
                "laureate_award_id": la_id,
                "authorized_member_id": mid,
                "submission_number": "ППЗ-QA-1",
            },
        )
        _assert_ok(ppz, (201,))
        ppz_id = ppz.json()["id"]
        _assert_ok(client.get("/api/voting/ppz-submissions"))
        _assert_ok(client.get(f"/api/voting/ppz-submissions/{ppz_id}/docx"))

        # ── Reports (дублируют часть laureates/awards, но клиент ходит сюда) ─
        _assert_ok(client.get("/api/reports/award-lifecycle"))
        _assert_ok(client.get("/api/reports/warehouse-summary"))
        _assert_ok(client.get("/api/reports/awards-laureates"))
        _assert_ok(client.get("/api/reports/incomplete-lifecycle"))
        _assert_ok(client.get("/api/reports/lifecycle-by-stage"))
        _assert_ok(client.get("/api/reports/site-export"))
        _assert_ok(client.get("/api/reports/statistics"))

        # ── Access mirror ───────────────────────────────────────────────
        _assert_ok(client.get("/api/access-mirror/tables"))
        # data — 404 если зеркало пустое; это нормально
        r_data = client.get("/api/access-mirror/data", params={"table": "nonexistent_qa"})
        assert r_data.status_code in (404, 200)

        # ── Backup CSV (pg_dump может отсутствовать в CI) ─────────────────
        r_csv = client.get("/api/backup/export/csv/awards")
        _assert_ok(r_csv)
        assert b"," in r_csv.content or len(r_csv.content) == 0

        r_dump = client.get("/api/backup/export")
        assert r_dump.status_code in (200, 500)
        # Откат транзакции — в conftest; отдельный cleanup не нужен.
