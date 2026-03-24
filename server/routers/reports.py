from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from datetime import date

from database import get_db
from models.award import Award, AwardEstablishment, AwardDevelopment, InventoryItem
from models.laureate import Laureate, LaureateAward, LaureateLifecycle
from models.committee import CommitteeMember

router = APIRouter()


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


@router.get("/awards-laureates")
def awards_laureates(db: Session = Depends(get_db)):
    """Награды-лауреаты — все лауреаты, сгруппированные по награде."""
    awards = (
        db.query(Award)
        .options(
            joinedload(Award.laureate_awards).joinedload(LaureateAward.laureate),
        )
        .all()
    )
    result = []
    for a in awards:
        laureates = []
        for la in a.laureate_awards:
            laureates.append({
                "laureate_award_id": la.id,
                "laureate_id": la.laureate.id,
                "full_name": la.laureate.full_name,
                "category": la.laureate.category.value if la.laureate.category else None,
                "assigned_date": la.assigned_date,
                "status": la.status,
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
        lc = la.lifecycle
        if lc is None:
            result.append({
                "laureate_award_id": la.id,
                "laureate_name": la.laureate.full_name,
                "award_name": la.award.name,
                "incomplete_stages": [
                    "nomination", "voting", "decision",
                    "registration", "ceremony", "publication",
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


@router.get("/statistics")
def statistics(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Статистика по категориям лауреатов с фильтром по дате."""
    q = db.query(
        Laureate.category,
        func.count(Laureate.id).label("count"),
    )
    if from_date:
        q = q.filter(Laureate.created_at >= from_date)
    if to_date:
        q = q.filter(Laureate.created_at <= to_date)
    rows = q.group_by(Laureate.category).all()

    total = sum(r.count for r in rows)
    return {
        "total": total,
        "by_category": [
            {
                "category": r.category.value if r.category else None,
                "count": r.count,
                "percent": round(r.count / total * 100, 2) if total > 0 else 0,
            }
            for r in rows
        ],
    }
