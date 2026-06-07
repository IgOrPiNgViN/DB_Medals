"""Синхронизация флагов ЖЦ лауреата с учётом на складе (резерв / выдача)."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.award import Award, InventoryItem
from models.laureate import LaureateAward, LaureateLifecycle
from services.award_kits import kit_components_for_award


def _reconcile(item: InventoryItem) -> None:
    total = item.total_count or 0
    reserve = item.reserve_count or 0
    issued = item.issued_count or 0
    if reserve + issued > total:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Сумма резерва и выданного превышает остаток "
                f"({item.component_type.value if item.component_type else item.id})"
            ),
        )
    item.available_count = max(0, total - reserve - issued)


def _award_for_link(db: Session, laureate_award: LaureateAward) -> Award | None:
    if laureate_award.award is not None:
        return laureate_award.award
    return db.query(Award).filter(Award.id == laureate_award.award_id).first()


def _kit_inventory_items(
    db: Session,
    laureate_award: LaureateAward,
    kit_type_label: str | None = None,
) -> list[InventoryItem]:
    award = _award_for_link(db, laureate_award)
    q = db.query(InventoryItem).filter(InventoryItem.award_id == laureate_award.award_id)
    if award is not None:
        components = kit_components_for_award(award, kit_type_label)
        q = q.filter(InventoryItem.component_type.in_(components))
    return q.order_by(InventoryItem.id).all()


def reserve_for_laureate_award(
    db: Session,
    laureate_award: LaureateAward,
    *,
    kit_type_label: str | None = None,
) -> None:
    """Зарезервировать по 1 ед. каждого компонента комплекта."""
    items = _kit_inventory_items(db, laureate_award, kit_type_label)
    if not items:
        return
    for item in items:
        if (item.available_count or 0) < 1:
            comp = item.component_type.value if item.component_type else str(item.id)
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно на складе для компонента «{comp}»",
            )
        item.reserve_count = (item.reserve_count or 0) + 1
        _reconcile(item)


def issue_for_laureate_award(
    db: Session,
    laureate_award: LaureateAward,
    *,
    was_reserved: bool,
    kit_type_label: str | None = None,
) -> None:
    """Списать комплект: из резерва (если был) или напрямую в «выдано»."""
    items = _kit_inventory_items(db, laureate_award, kit_type_label)
    if not items:
        return
    for item in items:
        if was_reserved:
            reserve = item.reserve_count or 0
            if reserve < 1:
                comp = item.component_type.value if item.component_type else str(item.id)
                raise HTTPException(
                    status_code=400,
                    detail=f"Нет резерва для компонента «{comp}»",
                )
            item.reserve_count = reserve - 1
        elif (item.available_count or 0) < 1:
            comp = item.component_type.value if item.component_type else str(item.id)
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно на складе для компонента «{comp}»",
            )
        item.issued_count = (item.issued_count or 0) + 1
        _reconcile(item)


def apply_inventory_flags(
    db: Session,
    lc: LaureateLifecycle,
    *,
    old_reserved: bool,
    old_issued: bool,
    new_reserved: bool,
    new_issued: bool,
) -> None:
    la = lc.laureate_award
    if la is None:
        raise HTTPException(status_code=400, detail="LaureateAward not loaded")
    kit = lc.ceremony_kit_type

    if new_reserved and not old_reserved:
        reserve_for_laureate_award(db, la, kit_type_label=kit)
    if new_issued and not old_issued:
        issue_for_laureate_award(
            db, la, was_reserved=old_reserved or new_reserved, kit_type_label=kit,
        )


def auto_reserve_on_decision(db: Session, lc: LaureateLifecycle) -> bool:
    """Авто-резерв после этапа «Решение», если ещё не зарезервировано."""
    if lc.inventory_reserved or not lc.decision_done:
        return False
    la = lc.laureate_award
    if la is None:
        return False
    items = _kit_inventory_items(db, la, lc.ceremony_kit_type)
    if not items:
        lc.inventory_reserved = True
        return True
    reserve_for_laureate_award(db, la, kit_type_label=lc.ceremony_kit_type)
    lc.inventory_reserved = True
    return True


def auto_reserve_on_link(db: Session, lc: LaureateLifecycle) -> bool:
    """Авто-резерв при привязке награды к лауреату (ТЗ)."""
    if lc.inventory_reserved:
        return False
    la = lc.laureate_award
    if la is None:
        return False
    items = _kit_inventory_items(db, la, lc.ceremony_kit_type)
    if not items:
        lc.inventory_reserved = True
        return True
    reserve_for_laureate_award(db, la, kit_type_label=lc.ceremony_kit_type)
    lc.inventory_reserved = True
    return True
