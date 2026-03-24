from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models.award import (
    Award, AwardCharacteristic, AwardEstablishment,
    AwardDevelopment, AwardApproval, AwardProduction, InventoryItem,
)
from schemas.award import (
    AwardCreate, AwardUpdate, AwardRead,
    AwardCharacteristicCreate, AwardCharacteristicRead,
    AwardEstablishmentCreate, AwardEstablishmentRead,
    AwardDevelopmentCreate, AwardDevelopmentRead,
    AwardApprovalCreate, AwardApprovalRead,
    AwardProductionCreate, AwardProductionRead,
    InventoryItemCreate, InventoryItemRead,
)

router = APIRouter()


def _get_award_or_404(db: Session, award_id: int) -> Award:
    award = db.query(Award).filter(Award.id == award_id).first()
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")
    return award


# ── Award CRUD ──────────────────────────────────────────────────────────────

@router.get("/", response_model=List[AwardRead])
def list_awards(award_type: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Award)
    if award_type:
        q = q.filter(Award.award_type == award_type)
    return q.all()


@router.post("/", response_model=AwardRead, status_code=status.HTTP_201_CREATED)
def create_award(payload: AwardCreate, db: Session = Depends(get_db)):
    award = Award(**payload.model_dump())
    db.add(award)
    db.commit()
    db.refresh(award)
    return award


@router.get("/{award_id}", response_model=AwardRead)
def get_award(award_id: int, db: Session = Depends(get_db)):
    return _get_award_or_404(db, award_id)


@router.put("/{award_id}", response_model=AwardRead)
def update_award(award_id: int, payload: AwardUpdate, db: Session = Depends(get_db)):
    award = _get_award_or_404(db, award_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(award, key, value)
    db.commit()
    db.refresh(award)
    return award


@router.delete("/{award_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_award(award_id: int, db: Session = Depends(get_db)):
    award = _get_award_or_404(db, award_id)
    db.delete(award)
    db.commit()


# ── Characteristics ─────────────────────────────────────────────────────────

@router.post(
    "/{award_id}/characteristics",
    response_model=AwardCharacteristicRead,
    status_code=status.HTTP_201_CREATED,
)
def create_characteristic(
    award_id: int, payload: AwardCharacteristicCreate, db: Session = Depends(get_db),
):
    _get_award_or_404(db, award_id)
    obj = AwardCharacteristic(**payload.model_dump())
    obj.award_id = award_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{award_id}/characteristics", response_model=List[AwardCharacteristicRead])
def list_characteristics(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    return db.query(AwardCharacteristic).filter(
        AwardCharacteristic.award_id == award_id,
    ).all()


# ── Establishment ───────────────────────────────────────────────────────────

@router.post(
    "/{award_id}/establishment",
    response_model=AwardEstablishmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_establishment(
    award_id: int, payload: AwardEstablishmentCreate, db: Session = Depends(get_db),
):
    _get_award_or_404(db, award_id)
    existing = db.query(AwardEstablishment).filter(
        AwardEstablishment.award_id == award_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Establishment already exists for this award")
    obj = AwardEstablishment(**payload.model_dump())
    obj.award_id = award_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{award_id}/establishment", response_model=AwardEstablishmentRead)
def get_establishment(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    obj = db.query(AwardEstablishment).filter(
        AwardEstablishment.award_id == award_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Establishment not found")
    return obj


@router.put("/{award_id}/establishment", response_model=AwardEstablishmentRead)
def update_establishment(
    award_id: int, payload: AwardEstablishmentCreate, db: Session = Depends(get_db),
):
    obj = db.query(AwardEstablishment).filter(
        AwardEstablishment.award_id == award_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Establishment not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key != "award_id":
            setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


# ── Development ─────────────────────────────────────────────────────────────

@router.post(
    "/{award_id}/development",
    response_model=AwardDevelopmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_development(
    award_id: int, payload: AwardDevelopmentCreate, db: Session = Depends(get_db),
):
    _get_award_or_404(db, award_id)
    existing = db.query(AwardDevelopment).filter(
        AwardDevelopment.award_id == award_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Development already exists for this award")
    obj = AwardDevelopment(**payload.model_dump())
    obj.award_id = award_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{award_id}/development", response_model=AwardDevelopmentRead)
def get_development(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    obj = db.query(AwardDevelopment).filter(
        AwardDevelopment.award_id == award_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Development not found")
    return obj


@router.put("/{award_id}/development", response_model=AwardDevelopmentRead)
def update_development(
    award_id: int, payload: AwardDevelopmentCreate, db: Session = Depends(get_db),
):
    obj = db.query(AwardDevelopment).filter(
        AwardDevelopment.award_id == award_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Development not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key != "award_id":
            setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


# ── Approvals ───────────────────────────────────────────────────────────────

@router.post(
    "/{award_id}/approvals",
    response_model=AwardApprovalRead,
    status_code=status.HTTP_201_CREATED,
)
def create_approval(
    award_id: int, payload: AwardApprovalCreate, db: Session = Depends(get_db),
):
    _get_award_or_404(db, award_id)
    obj = AwardApproval(**payload.model_dump())
    obj.award_id = award_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{award_id}/approvals", response_model=List[AwardApprovalRead])
def list_approvals(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    return db.query(AwardApproval).filter(AwardApproval.award_id == award_id).all()


# ── Productions ─────────────────────────────────────────────────────────────

@router.post(
    "/{award_id}/productions",
    response_model=AwardProductionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_production(
    award_id: int, payload: AwardProductionCreate, db: Session = Depends(get_db),
):
    _get_award_or_404(db, award_id)
    obj = AwardProduction(**payload.model_dump())
    obj.award_id = award_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{award_id}/productions", response_model=List[AwardProductionRead])
def list_productions(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    return db.query(AwardProduction).filter(AwardProduction.award_id == award_id).all()


# ── Inventory ───────────────────────────────────────────────────────────────

@router.post(
    "/{award_id}/inventory",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inventory_item(
    award_id: int, payload: InventoryItemCreate, db: Session = Depends(get_db),
):
    _get_award_or_404(db, award_id)
    obj = InventoryItem(**payload.model_dump())
    obj.award_id = award_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{award_id}/inventory", response_model=List[InventoryItemRead])
def list_inventory(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    return db.query(InventoryItem).filter(InventoryItem.award_id == award_id).all()


@router.put("/inventory/{item_id}", response_model=InventoryItemRead)
def update_inventory_item(
    item_id: int, payload: InventoryItemCreate, db: Session = Depends(get_db),
):
    obj = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


# ── Reports ─────────────────────────────────────────────────────────────────

@router.get("/lifecycle")
def award_lifecycle_report(db: Session = Depends(get_db)):
    """Жизненный цикл наград — сводная таблица по всем наградам."""
    awards = db.query(Award).all()
    result = []
    for a in awards:
        result.append({
            "id": a.id,
            "name": a.name,
            "award_type": a.award_type.value if a.award_type else None,
            "has_establishment": a.establishment is not None,
            "establishment_date": (
                a.establishment.establishment_date if a.establishment else None
            ),
            "has_development": a.development is not None,
            "development_status": (
                a.development.status if a.development else None
            ),
            "approvals_count": len(a.approvals),
            "productions_count": len(a.productions),
            "inventory_total": sum(i.total_count or 0 for i in a.inventory_items),
        })
    return result


@router.get("/warehouse")
def warehouse_report(db: Session = Depends(get_db)):
    """Сводка по складу с предупреждениями о низких остатках (< 10)."""
    items = db.query(InventoryItem).all()
    result = []
    for it in items:
        result.append({
            "id": it.id,
            "award_id": it.award_id,
            "component_type": it.component_type.value if it.component_type else None,
            "total_count": it.total_count,
            "reserve_count": it.reserve_count,
            "issued_count": it.issued_count,
            "available_count": it.available_count,
            "low_stock": (it.available_count or 0) < 10,
        })
    return result
