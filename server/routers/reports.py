from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from typing import Optional
from datetime import date, datetime, timezone, timedelta

from database import get_db
from models.award import Award, AwardApproval, AwardEstablishment, AwardDevelopment, InventoryItem, KitDisposal
from models.laureate import Laureate, LaureateAward, LaureateLifecycle
from models.committee import CommitteeMember
from services.excel_export import rows_to_xlsx
from services.warehouse_aggregate import (
    warehouse_summary_grouped,
    grouped_xlsx_headers,
    grouped_xlsx_row,
)
from models.award import AwardType

router = APIRouter()


def _valid_bulletin_number(value: str | None) -> bool:
    bn = (value or "").strip()
    return bool(bn) and bn != "0"


def _lc_report_row(la: LaureateAward, lc: LaureateLifecycle | None) -> dict:
    return {
        "laureate_award_id": la.id,
        "laureate_name": la.laureate.full_name if la.laureate else "",
        "award_name": la.award.name if la.award else "",
        "decision_date": lc.decision_date if lc else None,
        "registration_date": lc.registration_date if lc else None,
        "ceremony_date": lc.ceremony_date if lc else None,
        "publication_date": lc.publication_date if lc else None,
        "publication_nk_link": lc.publication_nk_link if lc else None,
        "publication_smi_web_count": lc.publication_smi_web_count if lc else 0,
        "publication_smi_print_count": lc.publication_smi_print_count if lc else 0,
        "voting_bulletin_number": lc.voting_bulletin_number if lc else None,
    }


def _tz_queue_section(lc: LaureateLifecycle | None) -> str | None:
    """Очередь по ТЗ: голосование → оформление → вручение → опубликование."""
    if lc is None:
        return "for_voting"
    if not lc.voting_done or not lc.decision_done:
        return "for_voting"
    if not lc.registration_done or not getattr(lc, "consent_received", False):
        return "for_registration"
    if not lc.ceremony_done:
        return "for_ceremony"
    if not lc.publication_done:
        return "for_publication"
    return None


_LC_SECTION_LABELS = {
    "for_voting": "На голосование",
    "for_registration": "На оформление",
    "for_ceremony": "На вручение",
    "for_publication": "На опубликование",
}


@router.get("/award-lifecycle")
def award_lifecycle(db: Session = Depends(get_db)):
    """Жизненный цикл наград — сводная таблица."""
    awards = (
        db.query(Award)
        .options(
            joinedload(Award.establishment),
            joinedload(Award.development),
            joinedload(Award.approvals),
            joinedload(Award.productions),
            joinedload(Award.inventory_items),
        )
        .all()
    )
    result = []
    for a in awards:
        result.append({
            "id": a.id,
            "name": a.name,
            "award_type": a.award_type.value if a.award_type else None,
            "establishment": {
                "date": a.establishment.establishment_date,
                "document": a.establishment.document_number,
            } if a.establishment else None,
            "development": {
                "developer": a.development.developer,
                "status": a.development.status,
                "start": a.development.start_date,
                "end": a.development.end_date,
            } if a.development else None,
            "approvals_count": len(a.approvals),
            "productions_count": len(a.productions),
            "inventory_summary": [
                {
                    "component": i.component_type.value if i.component_type else None,
                    "total": i.total_count,
                    "available": i.available_count,
                }
                for i in a.inventory_items
            ],
        })
    return result


@router.get("/warehouse-summary")
def warehouse_summary(db: Session = Depends(get_db)):
    """Сводка по складу с предупреждениями о низких остатках."""
    items = (
        db.query(InventoryItem)
        .options(joinedload(InventoryItem.award))
        .all()
    )
    result = []
    for it in items:
        result.append({
            "id": it.id,
            "award_id": it.award_id,
            "award_name": it.award.name if it.award else None,
            "component_type": it.component_type.value if it.component_type else None,
            "total_count": it.total_count,
            "reserve_count": it.reserve_count,
            "issued_count": it.issued_count,
            "available_count": it.available_count,
            "low_stock": (it.available_count or 0) < 10,
        })
    return result


@router.get("/warehouse-summary-grouped")
def warehouse_summary_grouped_route(
    award_type: Optional[str] = Query(None, description="medal|ppz|distinction|decoration"),
    db: Session = Depends(get_db),
):
    """Сводка склада по наградам — колонки как в ТЗ (file-011)."""
    return warehouse_summary_grouped(db, award_type)


@router.get("/warehouse-summary-grouped.xlsx")
def warehouse_summary_grouped_xlsx(
    award_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    items = warehouse_summary_grouped(db, award_type)
    headers = grouped_xlsx_headers(award_type)
    rows = [grouped_xlsx_row(it) for it in items]
    return rows_to_xlsx(headers, rows, filename="warehouse_grouped.xlsx")


@router.get("/awards-laureates")
def awards_laureates(
    award_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Награды-лауреаты — все лауреаты, сгруппированные по награде."""
    q = (
        db.query(Award)
        .options(
            joinedload(Award.laureate_awards).joinedload(LaureateAward.laureate),
            joinedload(Award.laureate_awards).joinedload(LaureateAward.lifecycle),
        )
    )
    if award_id is not None:
        q = q.filter(Award.id == award_id)
    awards = q.order_by(Award.name).all()
    result = []
    for a in awards:
        laureates = []
        for la in a.laureate_awards:
            if la.laureate is None:
                continue
            lc = la.lifecycle
            protocol_number = None
            protocol_date = None
            if lc:
                protocol_number = lc.decision_protocol_number or lc.registration_protocol_number
                protocol_date = lc.decision_date or lc.registration_date
            laureates.append({
                "laureate_award_id": la.id,
                "laureate_id": la.laureate.id,
                "full_name": la.laureate.full_name,
                "position": la.laureate.position,
                "organization": la.laureate.organization,
                "category": la.laureate.category.value if la.laureate.category else None,
                "assigned_date": la.assigned_date,
                "status": la.status,
                "protocol_number": protocol_number,
                "protocol_date": protocol_date,
                "ceremony_date": lc.ceremony_date if lc else None,
                "handed_over": bool(lc.ceremony_done) if lc else False,
            })
        result.append({
            "award_id": a.id,
            "award_name": a.name,
            "award_type": a.award_type.value if a.award_type else None,
            "laureates_count": len(laureates),
            "laureates": laureates,
        })
    return result


@router.get("/incomplete-lifecycle")
def incomplete_lifecycle(db: Session = Depends(get_db)):
    """Незавершённый жизненный цикл — лауреаты с недоделанными этапами."""
    la_list = (
        db.query(LaureateAward)
        .options(
            joinedload(LaureateAward.laureate),
            joinedload(LaureateAward.award),
            joinedload(LaureateAward.lifecycle),
        )
        .all()
    )
    result = []
    for la in la_list:
        if la.laureate is None or la.award is None:
            continue
        lc = la.lifecycle
        if lc is None:
            result.append({
                "laureate_award_id": la.id,
                "laureate_name": la.laureate.full_name,
                "award_name": la.award.name,
                "incomplete_stages": [
                    "nomination", "voting", "decision",
                    "registration", "consent_pd", "ceremony", "publication",
                ],
            })
            continue
        stages = []
        if not lc.nomination_done:
            stages.append("nomination")
        if not lc.voting_done:
            stages.append("voting")
        if not lc.decision_done:
            stages.append("decision")
        if not lc.registration_done:
            stages.append("registration")
        if not getattr(lc, "consent_received", False):
            stages.append("consent_pd")
        if not lc.ceremony_done:
            stages.append("ceremony")
        if not lc.publication_done:
            stages.append("publication")
        if stages:
            result.append({
                "laureate_award_id": la.id,
                "laureate_name": la.laureate.full_name,
                "award_name": la.award.name,
                "incomplete_stages": stages,
            })
    return result


@router.get("/incomplete-lifecycle-sections")
def incomplete_lifecycle_sections(db: Session = Depends(get_db)):
    """Незавершённый ЖЦ — 4 очереди по ТЗ (file-019, file-020)."""
    la_list = (
        db.query(LaureateAward)
        .options(
            joinedload(LaureateAward.laureate),
            joinedload(LaureateAward.award),
            joinedload(LaureateAward.lifecycle),
        )
        .all()
    )
    sections = {k: [] for k in _LC_SECTION_LABELS}
    for la in la_list:
        if la.laureate is None or la.award is None:
            continue
        key = _tz_queue_section(la.lifecycle)
        if key is None:
            continue
        sections[key].append(_lc_report_row(la, la.lifecycle))
    return {
        "sections": sections,
        "counts": {k: len(v) for k, v in sections.items()},
    }


@router.get("/incomplete-lifecycle-sections.xlsx")
def incomplete_lifecycle_sections_xlsx(db: Session = Depends(get_db)):
    data = incomplete_lifecycle_sections(db)
    headers = [
        "ФИО", "Награда", "Присуждение", "Оформление", "Вручение",
        "Опубликование НК", "Сайты СМИ", "Бум. СМИ",
    ]
    rows_out = []
    for key in _LC_SECTION_LABELS:
        label = _LC_SECTION_LABELS[key]
        rows_out.append([f"=== {label} ==="] + [""] * (len(headers) - 1))
        for r in data["sections"].get(key, []):
            rows_out.append([
                r["laureate_name"],
                r["award_name"],
                r.get("decision_date"),
                r.get("registration_date"),
                r.get("ceremony_date"),
                r.get("publication_date"),
                r.get("publication_smi_web_count"),
                r.get("publication_smi_print_count"),
            ])
        rows_out.append([""] * len(headers))
    return rows_to_xlsx(headers, rows_out, filename="incomplete_lifecycle_sections.xlsx")


@router.get("/warehouse-summary.xlsx")
def warehouse_summary_xlsx(db: Session = Depends(get_db)):
    items = warehouse_summary(db)
    headers = ["Награда", "Компонент", "Всего", "Резерв", "Выдано", "Доступно", "Мало (<10)"]
    rows = [
        [
            it.get("award_name"),
            it.get("component_type"),
            it.get("total_count"),
            it.get("reserve_count"),
            it.get("issued_count"),
            it.get("available_count"),
            "да" if it.get("low_stock") else "",
        ]
        for it in items
    ]
    return rows_to_xlsx(headers, rows, filename="warehouse_summary.xlsx")


@router.get("/awards-laureates.xlsx")
def awards_laureates_xlsx(
    award_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    groups = awards_laureates(db)
    if award_id is not None:
        groups = [g for g in groups if g.get("award_id") == award_id]
    headers = [
        "Награда", "ФИО", "Должность", "Организация",
        "№ протокола", "Дата проток.", "Вручение", "Дата вручения",
    ]
    rows = []
    for g in groups:
        for la in g.get("laureates") or []:
            rows.append([
                g.get("award_name"),
                la.get("full_name"),
                la.get("position"),
                la.get("organization"),
                la.get("protocol_number"),
                la.get("protocol_date"),
                "Да" if la.get("handed_over") else "Нет",
                la.get("ceremony_date"),
            ])
    return rows_to_xlsx(headers, rows, filename="awards_laureates.xlsx")


_STAGE_ORDER = [
    "nomination",
    "voting",
    "decision",
    "registration",
    "ceremony",
    "publication",
]


def _first_open_stage(lc: LaureateLifecycle | None) -> str:
    """Текущий (первый незакрытый) этап ЖЦ лауреата; все закрыты — «complete»."""
    if lc is None:
        return "nomination"
    if not lc.nomination_done:
        return "nomination"
    if not lc.voting_done:
        return "voting"
    if not lc.decision_done:
        return "decision"
    if not lc.registration_done:
        return "registration"
    if not lc.ceremony_done:
        return "ceremony"
    if not lc.publication_done:
        return "publication"
    return "complete"


@router.get("/lifecycle-by-stage")
def lifecycle_by_stage(db: Session = Depends(get_db)):
    """
    Сводка по этапам ЖЦ лауреата (ТЗ: сколько на этапе, список лауреатов).
    Каждая связка лауреат–награда отнесена к первому незавершённому этапу
    (или к «complete», если все этапы отмечены).
    """
    la_list = (
        db.query(LaureateAward)
        .options(
            joinedload(LaureateAward.laureate),
            joinedload(LaureateAward.award),
            joinedload(LaureateAward.lifecycle),
        )
        .all()
    )
    by_stage: dict[str, list[dict]] = {s: [] for s in _STAGE_ORDER}
    by_stage["complete"] = []

    for la in la_list:
        lc = la.lifecycle
        stage = _first_open_stage(lc)
        entry = {
            "laureate_award_id": la.id,
            "laureate_id": la.laureate_id,
            "laureate_name": la.laureate.full_name if la.laureate else "",
            "award_id": la.award_id,
            "award_name": la.award.name if la.award else "",
        }
        by_stage[stage].append(entry)

    counts = {k: len(v) for k, v in by_stage.items()}
    return {"counts": counts, "by_stage": by_stage}


@router.get("/site-export")
def site_export(db: Session = Depends(get_db)):
    """Минимальная выгрузка лауреатов и наград для публикации на сайте (опционально по ТЗ)."""
    la_list = (
        db.query(LaureateAward)
        .options(
            joinedload(LaureateAward.laureate),
            joinedload(LaureateAward.award),
        )
        .all()
    )
    items = []
    for la in la_list:
        items.append({
            "laureate_award_id": la.id,
            "laureate_name": la.laureate.full_name if la.laureate else "",
            "laureate_category": la.laureate.category.value if la.laureate and la.laureate.category else None,
            "award_name": la.award.name if la.award else "",
            "award_type": la.award.award_type.value if la.award and la.award.award_type else None,
            "assigned_date": la.assigned_date.isoformat() if la.assigned_date else None,
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }


@router.get("/warehouse-reservations")
def warehouse_reservations(db: Session = Depends(get_db)):
    """
    Резерв на складе без вручения и реестр выбытия (выдано лауреатам).
    """
    rows = (
        db.query(LaureateAward)
        .join(LaureateLifecycle, LaureateLifecycle.laureate_award_id == LaureateAward.id)
        .options(
            joinedload(LaureateAward.laureate),
            joinedload(LaureateAward.award),
            joinedload(LaureateAward.lifecycle),
        )
        .filter(
            (LaureateLifecycle.inventory_reserved.is_(True))
            | (LaureateLifecycle.inventory_issued.is_(True)),
        )
        .order_by(LaureateAward.id)
        .all()
    )
    reserved = []
    issued = []
    for la in rows:
        lc = la.lifecycle
        if lc is None:
            continue
        entry = {
            "laureate_award_id": la.id,
            "laureate_name": la.laureate.full_name if la.laureate else "",
            "award_name": la.award.name if la.award else "",
            "award_type": la.award.award_type.value if la.award and la.award.award_type else None,
            "assigned_date": la.assigned_date,
        }
        if lc.inventory_issued:
            issued.append(entry)
        elif lc.inventory_reserved:
            reserved.append(entry)

    postponed = []
    postponed_rows = (
        db.query(LaureateAward)
        .join(LaureateLifecycle, LaureateLifecycle.laureate_award_id == LaureateAward.id)
        .options(
            joinedload(LaureateAward.laureate),
            joinedload(LaureateAward.award),
        )
        .filter(LaureateLifecycle.registration_pending_issue.is_(True))
        .filter(
            or_(
                LaureateLifecycle.inventory_issued.is_(False),
                LaureateLifecycle.inventory_issued.is_(None),
            )
        )
        .order_by(LaureateAward.id)
        .all()
    )
    for la in postponed_rows:
        postponed.append({
            "laureate_award_id": la.id,
            "laureate_name": la.laureate.full_name if la.laureate else "",
            "award_name": la.award.name if la.award else "",
            "award_type": la.award.award_type.value if la.award and la.award.award_type else None,
            "assigned_date": la.assigned_date,
        })

    return {
        "reserved_pending": reserved,
        "postponed_pending": postponed,
        "issued_to_laureates": issued,
    }


@router.get("/kit-disposals-journal")
def kit_disposals_journal(db: Session = Depends(get_db)):
    """Журнал выбытия комплектов: лауреатам и «иное» (ТЗ file-012)."""
    rows = (
        db.query(KitDisposal)
        .options(
            joinedload(KitDisposal.award),
        )
        .order_by(KitDisposal.disposal_date.desc().nullslast(), KitDisposal.id.desc())
        .all()
    )
    la_ids = {r.laureate_award_id for r in rows if r.laureate_award_id}
    la_map: dict[int, LaureateAward] = {}
    if la_ids:
        for la in (
            db.query(LaureateAward)
            .options(joinedload(LaureateAward.laureate))
            .filter(LaureateAward.id.in_(la_ids))
            .all()
        ):
            la_map[la.id] = la

    laureate_items = []
    other_items = []
    for r in rows:
        la = la_map.get(r.laureate_award_id) if r.laureate_award_id else None
        entry = {
            "id": r.id,
            "award_id": r.award_id,
            "award_name": r.award.name if r.award else "",
            "quantity": r.quantity or 1,
            "disposal_date": r.disposal_date,
            "protocol_number": r.protocol_number,
            "event_name": r.event_name,
            "reason": r.reason,
            "note": r.note,
            "laureate_award_id": r.laureate_award_id,
            "laureate_name": la.laureate.full_name if la and la.laureate else "",
        }
        if (r.target or "").lower() == "laureate":
            laureate_items.append(entry)
        else:
            other_items.append(entry)

    return {
        "laureate_disposals": laureate_items,
        "other_disposals": other_items,
    }


@router.get("/approvals-monitor")
def approvals_monitor(
    approval_type: Optional[str] = Query(None, description="nk, heraldists, relatives, sponsors"),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Сводка согласований по всем наградам (ТЗ: мониторинг согласований НК)."""
    q = db.query(AwardApproval).options(joinedload(AwardApproval.award))
    if approval_type:
        q = q.filter(AwardApproval.approval_type == approval_type)
    if status:
        q = q.filter(AwardApproval.status.ilike(f"%{status.strip()}%"))
    rows = q.order_by(AwardApproval.date.desc().nullslast(), AwardApproval.id.desc()).all()
    return [
        {
            "id": a.id,
            "award_id": a.award_id,
            "award_name": a.award.name if a.award else "",
            "award_type": a.award.award_type.value if a.award and a.award.award_type else None,
            "approval_type": a.approval_type.value if a.approval_type else None,
            "approver_name": a.approver_name,
            "status": a.status,
            "date": a.date,
            "details": a.details,
        }
        for a in rows
    ]


@router.get("/awards-by-bulletin")
def awards_by_bulletin(db: Session = Depends(get_db)):
    """Связки лауреат–награда, сгруппированные по номеру бюллетеня (ТЗ)."""
    rows = (
        db.query(LaureateAward)
        .join(LaureateLifecycle, LaureateLifecycle.laureate_award_id == LaureateAward.id)
        .options(
            joinedload(LaureateAward.laureate),
            joinedload(LaureateAward.award),
            joinedload(LaureateAward.lifecycle),
        )
        .filter(LaureateLifecycle.voting_bulletin_number.isnot(None))
        .filter(LaureateLifecycle.voting_bulletin_number != "")
        .order_by(LaureateLifecycle.voting_bulletin_number, LaureateAward.id)
        .all()
    )
    by_bn: dict[str, list[dict]] = {}
    for la in rows:
        lc = la.lifecycle
        bn = (lc.voting_bulletin_number if lc else "") or ""
        bn = bn.strip()
        if not _valid_bulletin_number(bn):
            continue
        by_bn.setdefault(bn, []).append({
            "laureate_award_id": la.id,
            "laureate_name": la.laureate.full_name if la.laureate else "",
            "award_name": la.award.name if la.award else "",
            "award_type": la.award.award_type.value if la.award and la.award.award_type else None,
            "assigned_date": la.assigned_date,
            "bulletin_number": bn,
        })
    groups = [
        {"bulletin_number": bn, "count": len(items), "items": items}
        for bn, items in sorted(by_bn.items(), key=lambda x: x[0])
    ]
    return {
        "groups": groups,
        "total_links": sum(g["count"] for g in groups),
    }


@router.get("/statistics")
def statistics(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    award_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Статистика по категориям лауреатов (ТЗ file-022) с фильтром по награде."""
    q = (
        db.query(Laureate, LaureateAward, Award)
        .join(LaureateAward, LaureateAward.laureate_id == Laureate.id)
        .join(Award, Award.id == LaureateAward.award_id)
    )
    if from_date:
        q = q.filter(LaureateAward.assigned_date >= from_date)
    if to_date:
        q = q.filter(LaureateAward.assigned_date <= to_date)
    if award_id is not None:
        q = q.filter(Award.id == award_id)

    rows = q.order_by(Laureate.full_name).all()
    laureate_ids = set()
    by_category: dict[str, list[dict]] = {}
    for laureate, la, award in rows:
        laureate_ids.add(laureate.id)
        cat = laureate.category.value if laureate.category else "unknown"
        by_category.setdefault(cat, []).append({
            "full_name": laureate.full_name,
            "organization": laureate.organization,
            "award_name": award.name,
            "laureate_award_id": la.id,
        })

    total = len(laureate_ids)

    def _pct(part: int, whole: int) -> float:
        return round(part / whole * 100, 2) if whole > 0 else 0.0

    category_labels = {
        "employee": "Сотрудники",
        "veteran": "Ветераны",
        "university": "Университеты",
        "nii": "НИИ",
        "nonprofit": "Некомм. орг.",
        "commercial": "Комм. орг.",
    }

    physical_cats = ("employee", "veteran")
    legal_cats = ("university", "nii", "nonprofit", "commercial")

    def _subgroup(cats: tuple[str, ...], group_label: str) -> dict:
        members: set[int] = set()
        subgroups = []
        group_rows: list[dict] = []
        for cat in cats:
            cat_rows = by_category.get(cat, [])
            if not cat_rows:
                continue
            cat_laureates = {r["full_name"] for r in cat_rows}
            for r in cat_rows:
                members.add(r["full_name"])
                group_rows.append(r)
            subgroups.append({
                "key": cat,
                "label": category_labels.get(cat, cat),
                "count": len(cat_laureates),
                "percent_of_group": 0,
                "percent_of_total": _pct(len(cat_laureates), total),
                "rows": cat_rows,
            })
        group_count = len(members)
        for sg in subgroups:
            sg["percent_of_group"] = _pct(sg["count"], group_count)
        return {
            "key": group_label,
            "label": "Физические лица" if group_label == "physical" else "Юридические лица",
            "count": group_count,
            "percent_of_total": _pct(group_count, total),
            "subgroups": subgroups,
            "rows": group_rows,
        }

    groups = [
        _subgroup(physical_cats, "physical"),
        _subgroup(legal_cats, "legal"),
    ]

    by_category_summary = []
    for cat, cat_rows in sorted(by_category.items()):
        unique = len({r["full_name"] for r in cat_rows})
        by_category_summary.append({
            "category": cat,
            "count": unique,
            "percent": _pct(unique, total),
        })

    award_name = None
    if award_id is not None:
        aw = db.query(Award).filter(Award.id == award_id).first()
        award_name = aw.name if aw else None

    return {
        "total": total,
        "award_id": award_id,
        "award_name": award_name,
        "by_category": by_category_summary,
        "groups": groups,
    }
