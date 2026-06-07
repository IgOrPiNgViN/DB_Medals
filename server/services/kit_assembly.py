"""Сборка и разборка физических комплектов на складе (ТЗ)."""

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.award import Award, AwardKitStock, InventoryItem
from models.laureate import LaureateAward, LaureateLifecycle
from services.award_kits import kit_components_for_award
from services.inventory_lc import _reconcile


def _get_stock(db: Session, award_id: int) -> AwardKitStock:
    row = db.query(AwardKitStock).filter(AwardKitStock.award_id == award_id).first()
    if row is None:
        row = AwardKitStock(award_id=award_id)
        db.add(row)
        db.flush()
    return row


def count_postponed_sets(db: Session, award_id: int) -> int:
    """«Отложено» — оформлено, но не вручено (registration_pending_issue)."""
    return (
        db.query(func.count(LaureateLifecycle.id))
        .join(LaureateAward, LaureateAward.id == LaureateLifecycle.laureate_award_id)
        .filter(
            LaureateAward.award_id == award_id,
            LaureateLifecycle.registration_pending_issue.is_(True),
        )
        .scalar()
        or 0
    )


def sync_postponed_sets(db: Session, award_id: int) -> int:
    count = count_postponed_sets(db, award_id)
    stock = _get_stock(db, award_id)
    stock.postponed_sets = count
    return count


def kit_status(db: Session, award: Award) -> dict:
    sync_postponed_sets(db, award.id)
    stock = db.query(AwardKitStock).filter(AwardKitStock.award_id == award.id).first()
    components = kit_components_for_award(award)
    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.award_id == award.id,
            InventoryItem.component_type.in_(components),
        )
        .all()
    )
    can_assemble = 0
    if items:
        can_assemble = min((it.available_count or 0) for it in items)
    reserved_debt = sum((it.reserve_count or 0) for it in items)
    return {
        "physical_sets": stock.physical_sets if stock else 0,
        "free_sets": stock.free_sets if stock else 0,
        "postponed_sets": stock.postponed_sets if stock else 0,
        "can_assemble_from_loose": can_assemble,
        "reserve_outstanding": reserved_debt,
    }


def assemble_sets(
    db: Session,
    award: Award,
    quantity: int,
    *,
    kit_type_label: str | None = None,
) -> dict:
    if quantity < 1:
        raise HTTPException(status_code=400, detail="Количество должно быть >= 1")
    components = kit_components_for_award(award, kit_type_label)
    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.award_id == award.id,
            InventoryItem.component_type.in_(components),
        )
        .all()
    )
    if not items:
        raise HTTPException(status_code=400, detail="Нет компонентов комплекта на складе")
    for item in items:
        if (item.available_count or 0) < quantity:
            comp = item.component_type.value if item.component_type else str(item.id)
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно «{comp}» для сборки {quantity} компл.",
            )
    for item in items:
        item.available_count = (item.available_count or 0) - quantity
        _reconcile(item)
    stock = _get_stock(db, award.id)
    stock.physical_sets = (stock.physical_sets or 0) + quantity
    stock.free_sets = (stock.free_sets or 0) + quantity
    return kit_status(db, award)


def disassemble_sets(
    db: Session,
    award: Award,
    quantity: int,
    *,
    kit_type_label: str | None = None,
) -> dict:
    if quantity < 1:
        raise HTTPException(status_code=400, detail="Количество должно быть >= 1")
    stock = _get_stock(db, award.id)
    free = stock.free_sets or 0
    if free < quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно свободных комплектов (есть {free})",
        )
    components = kit_components_for_award(award, kit_type_label)
    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.award_id == award.id,
            InventoryItem.component_type.in_(components),
        )
        .all()
    )
    for item in items:
        item.available_count = (item.available_count or 0) + quantity
        _reconcile(item)
    stock.physical_sets = max(0, (stock.physical_sets or 0) - quantity)
    stock.free_sets = free - quantity
    return kit_status(db, award)
