from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import date

from database import get_db
from pydantic import BaseModel
from models.award import (
    Award, AwardCharacteristic, AwardEstablishment,
    AwardDevelopment, AwardApproval, AwardProduction, InventoryItem, AwardType,
    DecorationDisposal, KitDisposal, ComponentType,
)
from services.award_kits import ensure_inventory_kit
from services.kit_assembly import assemble_sets, disassemble_sets, kit_status
from services.kit_disposals import (
    create_kit_disposal,
    get_universal_stock,
    transfer_universal_to_award,
)
from schemas.award import (
    AwardCreate, AwardUpdate, AwardRead, AwardDetailRead, AwardListItem,
    AwardCharacteristicCreate, AwardCharacteristicRead,
    AwardEstablishmentCreate, AwardEstablishmentRead,
    AwardDevelopmentCreate, AwardDevelopmentRead,
    AwardApprovalCreate, AwardApprovalRead, AwardApprovalUpdate,
    AwardProductionCreate, AwardProductionRead, AwardProductionUpdate,
    ProductionStagesResponse, ProductionComponentStages, ProductionComponentStagesUpdate,
    InventoryItemCreate, InventoryItemRead, InventoryItemUpdate,
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
    if len(data) >= 4 and data[:4] in (b"\x49\x49\x2a\x00", b"\x4d\x4d\x00\x2a"):
        return "image/tiff"
    if data[:2] == b"BM":
        return "image/bmp"
    return "application/octet-stream"


def _image_magic_at(data: bytes, pos: int = 0) -> bool:
    """По смещению pos — начинается ли известный растровый формат."""
    if pos < 0 or pos >= len(data):
        return False
    s = data[pos:]
    if len(s) < 4:
        return False
    if s[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if len(s) >= 3 and s[:3] == b"\xff\xd8\xff":
        return True
    if len(s) >= 6 and s[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if len(s) >= 12 and s[:4] == b"RIFF" and s[8:12] == b"WEBP":
        return True
    if len(s) >= 4 and s[:4] in (b"\x49\x49\x2a\x00", b"\x4d\x4d\x00\x2a"):
        return True
    if s[:2] == b"BM":
        return True
    return False


def _normalize_award_image_bytes(raw: bytes | bytearray | memoryview | None) -> bytes | None:
    """
    Достаёт «сырые» пиксели из поля БД.

    Access часто хранит OLE-обёртку вокруг JPEG/PNG — Qt не открывает такой blob
    напрямую. Ищем сигнатуру изображения в первых 64 KiB и отрезаем префикс.
    """
    if raw is None:
        return None
    b = bytes(raw)
    if len(b) < 4:
        return None
    if _image_magic_at(b, 0):
        return b
    limit = min(len(b), 65536)
    for i in range(1, limit - 4):
        if _image_magic_at(b, i):
            return b[i:]
    # Не нашли сигнатуру — отдаём как есть (редкие форматы / уже сырые данные)
    return b


def _award_side_has_image(blob: bytes | bytearray | memoryview | None) -> bool:
    if blob is None or len(blob) == 0:
        return False
    nb = _normalize_award_image_bytes(blob)
    if not nb:
        return False
    return _image_magic_at(nb, 0)


def _award_to_read(award: Award) -> AwardRead:
    return AwardRead(
        id=award.id,
        name=award.name,
        award_type=award.award_type,
        description=award.description,
        created_at=award.created_at,
        has_image=_award_side_has_image(award.image_front),
        has_image_back=_award_side_has_image(award.image_back),
        has_establishment=award.establishment is not None,
        has_development=award.development is not None,
    )


def _award_to_detail(award: Award) -> AwardDetailRead:
    base = _award_to_read(award)
    return AwardDetailRead(
        **base.model_dump(),
        establishment=award.establishment,
        development=award.development,
    )


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
                has_image=_award_side_has_image(a.image_front),
                has_image_back=_award_side_has_image(a.image_back),
            )
        )
    return out


@router.post("/", response_model=AwardRead, status_code=status.HTTP_201_CREATED)
def create_award(payload: AwardCreate, db: Session = Depends(get_db)):
    award = Award(**payload.model_dump())
    db.add(award)
    db.flush()
    ensure_inventory_kit(db, award.id, award.award_type)
    db.commit()
    db.refresh(award)
    return _award_to_read(award)


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


def _reconcile_inventory_counts(obj: InventoryItem) -> None:
    total = obj.total_count or 0
    reserve = obj.reserve_count or 0
    issued = obj.issued_count or 0
    if reserve + issued > total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сумма резерва и выданного не может превышать общее количество",
        )
    obj.available_count = max(0, total - reserve - issued)


@router.put("/inventory/{item_id}", response_model=InventoryItemRead)
def update_inventory_item(
    item_id: int, payload: InventoryItemUpdate, db: Session = Depends(get_db),
):
    obj = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    _reconcile_inventory_counts(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/productions/{production_id}", response_model=AwardProductionRead)
def update_production(
    production_id: int, payload: AwardProductionUpdate, db: Session = Depends(get_db),
):
    obj = db.query(AwardProduction).filter(AwardProduction.id == production_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Production record not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/productions/{production_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_production(production_id: int, db: Session = Depends(get_db)):
    obj = db.query(AwardProduction).filter(AwardProduction.id == production_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Production record not found")
    db.delete(obj)
    db.commit()
    return None


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
        "has_front": _award_side_has_image(award.image_front),
        "has_back": _award_side_has_image(award.image_back),
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
    raw = award.image_front if side == "front" else award.image_back
    if not raw:
        raise HTTPException(status_code=404, detail="Изображение не загружено")
    payload = _normalize_award_image_bytes(raw)
    if not payload:
        raise HTTPException(status_code=404, detail="Изображение не загружено")
    return Response(content=payload, media_type=_guess_image_mime(payload))


@router.get("/{award_id}", response_model=AwardDetailRead)
def get_award(award_id: int, db: Session = Depends(get_db)):
    award = (
        db.query(Award)
        .options(
            joinedload(Award.establishment),
            joinedload(Award.development),
        )
        .filter(Award.id == award_id)
        .first()
    )
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")
    return _award_to_detail(award)


@router.put("/{award_id}", response_model=AwardRead)
def update_award(award_id: int, payload: AwardUpdate, db: Session = Depends(get_db)):
    award = _get_award_or_404(db, award_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(award, key, value)
    db.commit()
    db.refresh(award)
    return _award_to_read(award)


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
    data = AwardEstablishmentRead.model_validate(obj).model_dump()
    data["has_protocol_file"] = bool(obj.protocol_data)
    return data


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


@router.put("/approvals/{approval_id}", response_model=AwardApprovalRead)
def update_approval(
    approval_id: int, payload: AwardApprovalUpdate, db: Session = Depends(get_db),
):
    obj = db.query(AwardApproval).filter(AwardApproval.id == approval_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Approval not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/approvals/{approval_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_approval(approval_id: int, db: Session = Depends(get_db)):
    obj = db.query(AwardApproval).filter(AwardApproval.id == approval_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Approval not found")
    db.delete(obj)
    db.commit()
    return None


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


PRODUCTION_COMPONENTS_BY_AWARD_TYPE = {
    "medal": ["medal", "badge", "cufflinks", "pendant"],
    "ppz": ["ppz"],
    "distinction": ["badge"],
    "decoration": ["cufflinks", "pendant"],
}


@router.get("/{award_id}/production-stages", response_model=ProductionStagesResponse)
def get_production_stages(award_id: int, db: Session = Depends(get_db)):
    from services.production_stages import list_components_for_award

    award = _get_award_or_404(db, award_id)
    at = award.award_type.value if award.award_type else "medal"
    components = PRODUCTION_COMPONENTS_BY_AWARD_TYPE.get(at, ["medal", "badge"])
    return list_components_for_award(db, award_id, components)


@router.put("/{award_id}/production-stages", response_model=ProductionComponentStages)
def update_production_stages(
    award_id: int, body: ProductionComponentStagesUpdate, db: Session = Depends(get_db),
):
    from services.production_stages import upsert_component

    _get_award_or_404(db, award_id)
    result = upsert_component(
        db,
        award_id,
        body.component_type,
        is_ready=body.is_ready,
        stages=[s.model_dump() for s in body.stages] if body.stages else None,
    )
    db.commit()
    return result


@router.get("/{award_id}/production-stages/{component_type}/{stage_key}/attachments")
def list_production_stage_attachments(
    award_id: int,
    component_type: str,
    stage_key: str,
    db: Session = Depends(get_db),
):
    from services.production_stage_files import list_attachments

    _get_award_or_404(db, award_id)
    return list_attachments(db, award_id, component_type, stage_key)


@router.post(
    "/{award_id}/production-stages/{component_type}/{stage_key}/attachments",
    status_code=status.HTTP_201_CREATED,
)
async def upload_production_stage_attachment(
    award_id: int,
    component_type: str,
    stage_key: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    from services.production_stage_files import upload_attachment

    _get_award_or_404(db, award_id)
    result = await upload_attachment(db, award_id, component_type, stage_key, file)
    db.commit()
    return result


@router.get("/production-stage-attachments/{attachment_id}")
def download_production_stage_attachment(attachment_id: int, db: Session = Depends(get_db)):
    from services.production_stage_files import get_attachment_or_404

    att = get_attachment_or_404(db, attachment_id)
    media = att.content_type or "application/octet-stream"
    return Response(
        content=bytes(att.data),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{att.filename}"'},
    )


@router.delete("/production-stage-attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_production_stage_attachment(attachment_id: int, db: Session = Depends(get_db)):
    from services.production_stage_files import delete_attachment

    delete_attachment(db, attachment_id)
    db.commit()


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
    _reconcile_inventory_counts(obj)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{award_id}/inventory", response_model=List[InventoryItemRead])
def list_inventory(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    return db.query(InventoryItem).filter(InventoryItem.award_id == award_id).all()


class _KitOpBody(BaseModel):
    quantity: int = 1
    kit_type: Optional[str] = None


@router.get("/{award_id}/inventory/kit-status")
def get_kit_status(award_id: int, db: Session = Depends(get_db)):
    award = _get_award_or_404(db, award_id)
    return kit_status(db, award)


@router.post("/{award_id}/inventory/assemble")
def assemble_inventory_kits(
    award_id: int, body: _KitOpBody, db: Session = Depends(get_db),
):
    award = _get_award_or_404(db, award_id)
    result = assemble_sets(db, award, body.quantity, kit_type_label=body.kit_type)
    db.commit()
    return result


@router.post("/{award_id}/inventory/disassemble")
def disassemble_inventory_kits(
    award_id: int, body: _KitOpBody, db: Session = Depends(get_db),
):
    award = _get_award_or_404(db, award_id)
    result = disassemble_sets(db, award, body.quantity, kit_type_label=body.kit_type)
    db.commit()
    return result


@router.post("/{award_id}/establishment/protocol-file", status_code=status.HTTP_204_NO_CONTENT)
async def upload_establishment_protocol(
    award_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    obj = db.query(AwardEstablishment).filter(AwardEstablishment.award_id == award_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Establishment not found")
    data = await file.read()
    obj.protocol_data = data
    obj.protocol_filename = file.filename or "protocol.bin"
    obj.protocol_content_type = file.content_type
    obj.has_protocol_data = True
    db.commit()


@router.get("/{award_id}/establishment/protocol-file")
def download_establishment_protocol(award_id: int, db: Session = Depends(get_db)):
    obj = db.query(AwardEstablishment).filter(AwardEstablishment.award_id == award_id).first()
    if not obj or not obj.protocol_data:
        raise HTTPException(status_code=404, detail="Protocol file not found")
    return Response(
        content=obj.protocol_data,
        media_type=obj.protocol_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{obj.protocol_filename or "protocol.bin"}"',
        },
    )


class _DecorationDisposalCreate(BaseModel):
    component_type: ComponentType
    target: str = "laureate"
    laureate_award_id: Optional[int] = None
    event_name: Optional[str] = None
    reason: Optional[str] = None
    disposal_date: Optional[date] = None
    note: Optional[str] = None


@router.get("/{award_id}/decoration-disposals")
def list_decoration_disposals(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    rows = (
        db.query(DecorationDisposal)
        .filter(DecorationDisposal.award_id == award_id)
        .order_by(DecorationDisposal.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "component_type": r.component_type.value if r.component_type else None,
            "target": r.target,
            "laureate_award_id": r.laureate_award_id,
            "event_name": r.event_name,
            "reason": r.reason,
            "disposal_date": r.disposal_date,
            "note": r.note,
        }
        for r in rows
    ]


@router.post("/{award_id}/decoration-disposals", status_code=status.HTTP_201_CREATED)
def create_decoration_disposal(
    award_id: int, body: _DecorationDisposalCreate, db: Session = Depends(get_db),
):
    award = _get_award_or_404(db, award_id)
    if award.award_type != AwardType.DECORATION:
        raise HTTPException(status_code=400, detail="Только для наград типа «Украшения»")
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.award_id == award_id,
            InventoryItem.component_type == body.component_type,
        )
        .first()
    )
    if item is None or (item.available_count or 0) < 1:
        raise HTTPException(status_code=400, detail="Недостаточно остатка на складе")
    item.available_count = (item.available_count or 0) - 1
    item.issued_count = (item.issued_count or 0) + 1
    _reconcile_inventory_counts(item)
    obj = DecorationDisposal(
        award_id=award_id,
        laureate_award_id=body.laureate_award_id,
        component_type=body.component_type,
        target=body.target,
        event_name=body.event_name,
        reason=body.reason,
        disposal_date=body.disposal_date,
        note=body.note,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return {"id": obj.id}


class _KitDisposalCreate(BaseModel):
    target: str = "other"
    quantity: int = 1
    laureate_award_id: Optional[int] = None
    event_name: Optional[str] = None
    reason: Optional[str] = None
    protocol_number: Optional[str] = None
    disposal_date: Optional[date] = None
    note: Optional[str] = None


@router.get("/{award_id}/kit-disposals")
def list_kit_disposals(award_id: int, db: Session = Depends(get_db)):
    _get_award_or_404(db, award_id)
    rows = (
        db.query(KitDisposal)
        .filter(KitDisposal.award_id == award_id)
        .order_by(KitDisposal.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "target": r.target,
            "quantity": r.quantity,
            "laureate_award_id": r.laureate_award_id,
            "event_name": r.event_name,
            "reason": r.reason,
            "protocol_number": r.protocol_number,
            "disposal_date": r.disposal_date,
            "note": r.note,
        }
        for r in rows
    ]


@router.post("/{award_id}/kit-disposals", status_code=status.HTTP_201_CREATED)
def register_kit_disposal(
    award_id: int, body: _KitDisposalCreate, db: Session = Depends(get_db),
):
    _get_award_or_404(db, award_id)
    obj = create_kit_disposal(
        db,
        award_id=award_id,
        target=body.target,
        quantity=body.quantity,
        laureate_award_id=body.laureate_award_id,
        event_name=body.event_name,
        reason=body.reason,
        protocol_number=body.protocol_number,
        disposal_date=body.disposal_date,
        note=body.note,
    )
    db.commit()
    db.refresh(obj)
    return {"id": obj.id}


class _UniversalStockUpdate(BaseModel):
    certificate_count: Optional[int] = None
    box_count: Optional[int] = None


@router.get("/universal-stock")
def read_universal_stock(db: Session = Depends(get_db)):
    row = get_universal_stock(db)
    return {
        "certificate_count": row.certificate_count or 0,
        "box_count": row.box_count or 0,
    }


@router.put("/universal-stock")
def update_universal_stock(body: _UniversalStockUpdate, db: Session = Depends(get_db)):
    row = get_universal_stock(db)
    if body.certificate_count is not None:
        row.certificate_count = max(0, int(body.certificate_count))
    if body.box_count is not None:
        row.box_count = max(0, int(body.box_count))
    db.commit()
    return {
        "certificate_count": row.certificate_count or 0,
        "box_count": row.box_count or 0,
    }


class _ToKitBody(BaseModel):
    component: str
    quantity: int = 1


@router.post("/{award_id}/inventory/to-kit")
def move_universal_to_kit(
    award_id: int, body: _ToKitBody, db: Session = Depends(get_db),
):
    _get_award_or_404(db, award_id)
    result = transfer_universal_to_award(
        db, award_id, body.component, body.quantity,
    )
    db.commit()
    return result
