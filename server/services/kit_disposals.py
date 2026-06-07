"""Журнал выбытия комплектов и универсальный склад (ТЗ file-012)."""

from datetime import date as dt_date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.award import AwardKitStock, KitDisposal, UniversalStock


def _get_stock(db: Session, award_id: int) -> AwardKitStock:
    row = db.query(AwardKitStock).filter(AwardKitStock.award_id == award_id).first()
    if row is None:
        row = AwardKitStock(award_id=award_id)
        db.add(row)
        db.flush()
    return row


def get_universal_stock(db: Session) -> UniversalStock:
    row = db.query(UniversalStock).filter(UniversalStock.id == 1).first()
    if row is None:
        row = UniversalStock(id=1, certificate_count=0, box_count=0)
        db.add(row)
        db.flush()
    return row


def _deduct_kits(stock: AwardKitStock, quantity: int) -> None:
    qty = max(1, quantity)
    free = stock.free_sets or 0
    physical = stock.physical_sets or 0
    if free + physical < qty:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно комплектов на складе (свободно {free}, всего {physical})",
        )
    take_free = min(free, qty)
    stock.free_sets = free - take_free
    remainder = qty - take_free
    if remainder:
        stock.physical_sets = physical - remainder


def create_kit_disposal(
    db: Session,
    *,
    award_id: int,
    target: str,
    quantity: int = 1,
    laureate_award_id: int | None = None,
    event_name: str | None = None,
    reason: str | None = None,
    protocol_number: str | None = None,
    disposal_date: dt_date | None = None,
    note: str | None = None,
) -> KitDisposal:
    tgt = (target or "other").strip().lower()
    if tgt not in ("laureate", "other"):
        raise HTTPException(status_code=400, detail="target must be laureate or other")
    qty = max(1, int(quantity or 1))

    if tgt == "other":
        stock = _get_stock(db, award_id)
        _deduct_kits(stock, qty)
    else:
        stock = _get_stock(db, award_id)
        _deduct_kits(stock, qty)

    obj = KitDisposal(
        award_id=award_id,
        laureate_award_id=laureate_award_id if tgt == "laureate" else None,
        target=tgt,
        event_name=(event_name or "").strip() or None,
        reason=(reason or "").strip() or None,
        protocol_number=(protocol_number or "").strip() or None,
        disposal_date=disposal_date,
        note=(note or "").strip() or None,
        quantity=qty,
    )
    db.add(obj)
    return obj


def transfer_universal_to_award(
    db: Session,
    award_id: int,
    component: str,
    quantity: int = 1,
) -> dict:
    """Перевод универсального удостоверения/коробки в комплект награды («В комплект»)."""
    from models.award import InventoryItem, ComponentType

    qty = max(1, int(quantity or 1))
    comp = (component or "").strip().lower()
    if comp not in ("certificate", "box"):
        raise HTTPException(status_code=400, detail="component must be certificate or box")
    ct = ComponentType.CERTIFICATE if comp == "certificate" else ComponentType.BOX

    universal = get_universal_stock(db)
    if comp == "certificate":
        if (universal.certificate_count or 0) < qty:
            raise HTTPException(status_code=400, detail="Недостаточно универсальных удостоверений")
        universal.certificate_count -= qty
    else:
        if (universal.box_count or 0) < qty:
            raise HTTPException(status_code=400, detail="Недостаточно универсальных коробок")
        universal.box_count -= qty

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.award_id == award_id, InventoryItem.component_type == ct)
        .first()
    )
    if item is None:
        item = InventoryItem(
            award_id=award_id,
            component_type=ct,
            total_count=0,
            reserve_count=0,
            issued_count=0,
            available_count=0,
        )
        db.add(item)
        db.flush()
    item.total_count = (item.total_count or 0) + qty
    item.available_count = (item.available_count or 0) + qty
    return {
        "component_type": ct.value,
        "quantity": qty,
        "universal_certificate": universal.certificate_count,
        "universal_box": universal.box_count,
    }
