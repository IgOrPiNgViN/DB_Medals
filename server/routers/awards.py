from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

from database import get_db
from models.award import (
    Award, AwardCharacteristic, AwardEstablishment,
    AwardDevelopment, AwardApproval, AwardProduction, InventoryItem, AwardType,
)
from schemas.award import (
    AwardCreate, AwardUpdate, AwardRead, AwardListItem,
    AwardCharacteristicCreate, AwardCharacteristicRead,
    AwardEstablishmentCreate, AwardEstablishmentRead,
    AwardDevelopmentCreate, AwardDevelopmentRead,
    AwardApprovalCreate, AwardApprovalRead,
    AwardProductionCreate, AwardProductionRead,
    InventoryItemCreate, InventoryItemRead,
)

router = APIRouter()

# Вкладки PyQt («Медали», «ППЗ», …) группируют по этим строкам, не по enum .value.
_AWARD_TYPE_TAB_RU = {
    AwardType.MEDAL: "Медали",
    AwardType.PPZ: "ППЗ",
    AwardType.DISTINCTION: "Знаки отличия",
    AwardType.DECORATION: "Украшения",
}


def _award_type_tab_ru(award_type: AwardType | None) -> str:
    if award_type is None:
        return ""
    return _AWARD_TYPE_TAB_RU.get(award_type, award_type.value)


_TAB_RU_TO_ENUM = {v: k for k, v in _AWARD_TYPE_TAB_RU.items()}


def _guess_image_mime(data: bytes) -> str:
    if not data or len(data) < 4:
        return "application/octet-stream"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _get_award_or_404(db: Session, award_id: int) -> Award:
    award = db.query(Award).filter(Award.id == award_id).first()
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")
    return award


# ── Award CRUD ──────────────────────────────────────────────────────────────

@router.get("/", response_model=List[AwardListItem])
def list_awards(award_type: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Award)
    if award_type:
        en = _TAB_RU_TO_ENUM.get(award_type)
        if en is not None:
            q = q.filter(Award.award_type == en)
        else:
            try:
                q = q.filter(Award.award_type == AwardType(award_type))
            except ValueError:
                pass
    out: List[AwardListItem] = []
    for a in q.order_by(Award.name).all():
        out.append(
            AwardListItem(
                id=a.id,
                name=a.name,
                award_type=a.award_type,
                description=a.description,
                created_at=a.created_at,
                has_image=bool(a.image_front and len(a.image_front) > 0),
                has_image_back=bool(a.image_back and len(a.image_back) > 0),
            )
        )
    return out


@router.post("/", response_model=AwardRead, status_code=status.HTTP_201_CREATED)
def create_award(payload: AwardCreate, db: Session = Depends(get_db)):
    award = Award(**payload.model_dump())
    db.add(award)
    db.commit()
    db.refresh(award)
    return award


# ── Reports (до /{award_id}, иначе «lifecycle» и «warehouse» попадают в int → 422) ──

@router.get("/lifecycle")
def award_lifecycle_report(db: Session = Depends(get_db)):
    """Жизненный цикл наград — сводная таблица по всем наградам."""
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
        est = a.establishment
        if est:
            establishment = " ".join(
                x for x in (
                    str(est.establishment_date) if est.establishment_date else None,
                    f"№{est.document_number}" if est.document_number else None,
                )
                if x
            ) or "есть"
        else:
            establishment = "—"
        dev = a.development
        development = (dev.status or "—") if dev else "—"
        inv_total = sum((i.total_count or 0) for i in a.inventory_items)
        status = "На складе" if inv_total > 0 else "Без остатков"
        result.append({
            "id": a.id,
            "name": a.name,
            "award_type": _award_type_tab_ru(a.award_type),
            "establishment": establishment,
            "development": development,
            "approval": f"{len(a.approvals)} записей",
            "production": f"{len(a.productions)} записей",
            "status": status,
        })
    return result


@router.get("/warehouse")
def warehouse_report(db: Session = Depends(get_db)):
    """Сводка по складу с предупреждениями о низких остатках (< 10)."""
    items = (
        db.query(InventoryItem)
        .options(joinedload(InventoryItem.award))
        .all()
    )
    result = []
    for it in items:
        a = it.award
        ct = it.component_type.value if it.component_type else ""
        total = it.total_count or 0
        reserve = it.reserve_count or 0
        issued = it.issued_count or 0
        available = it.available_count or 0
        result.append({
            "id": it.id,
            "award_id": it.award_id,
            "award_name": a.name if a else "",
            "award_type": _award_type_tab_ru(a.award_type) if a else "",
            "component_type": ct,
            "total": total,
            "reserve": reserve,
            "issued": issued,
            "available": available,
            "total_count": total,
            "reserve_count": reserve,
            "issued_count": issued,
            "available_count": available,
            "low_stock": available < 10,
        })
    return result


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


@router.post("/{award_id}/images")
async def upload_award_images(
    award_id: int,
    image_front: UploadFile | None = File(None),
    image_back: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """Загрузка изображений лица и/или оборота (multipart)."""
    award = _get_award_or_404(db, award_id)
    if image_front is not None and image_front.filename:
        award.image_front = await image_front.read()
    if image_back is not None and image_back.filename:
        award.image_back = await image_back.read()
    db.commit()
    db.refresh(award)
    return {
        "status": "ok",
        "has_front": bool(award.image_front and len(award.image_front) > 0),
        "has_back": bool(award.image_back and len(award.image_back) > 0),
    }


@router.delete("/{award_id}/images/{side}")
def delete_award_image_side(award_id: int, side: str, db: Session = Depends(get_db)):
    if side not in ("front", "back"):
        raise HTTPException(status_code=400, detail="side must be front or back")
    award = _get_award_or_404(db, award_id)
    if side == "front":
        award.image_front = None
    else:
        award.image_back = None
    db.commit()
    return {"status": "ok"}


@router.get("/{award_id}/image")
def get_award_image(
    award_id: int,
    side: str = Query("front", description="front или back"),
    db: Session = Depends(get_db),
):
    """Изображение награды (лицо или оборот), бинарные данные из БД."""
    if side not in ("front", "back"):
        raise HTTPException(status_code=400, detail="side must be front or back")
    award = _get_award_or_404(db, award_id)
    data = award.image_front if side == "front" else award.image_back
    if not data:
        raise HTTPException(status_code=404, detail="Изображение не загружено")
    return Response(content=bytes(data), media_type=_guess_image_mime(bytes(data)))


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
