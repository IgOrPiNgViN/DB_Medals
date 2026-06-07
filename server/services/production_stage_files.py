"""Файлы вложений этапов производства."""

from __future__ import annotations

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from models.award import ProductionStageAttachment, ProductionStageRow
from services.production_stages import PRODUCTION_STAGES


def _valid_stage_key(stage_key: str) -> str:
    key = (stage_key or "").strip()
    valid = {k for k, _ in PRODUCTION_STAGES}
    if key not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown stage_key: {stage_key}")
    return key


def get_or_create_stage_row(
    db: Session,
    award_id: int,
    component_type: str,
    stage_key: str,
) -> ProductionStageRow:
    key = _valid_stage_key(stage_key)
    comp = (component_type or "").strip()
    row = (
        db.query(ProductionStageRow)
        .filter(
            ProductionStageRow.award_id == award_id,
            ProductionStageRow.component_type == comp,
            ProductionStageRow.stage_key == key,
        )
        .first()
    )
    if row is None:
        row = ProductionStageRow(
            award_id=award_id,
            component_type=comp,
            stage_key=key,
        )
        db.add(row)
        db.flush()
    return row


def list_attachments(
    db: Session,
    award_id: int,
    component_type: str,
    stage_key: str,
) -> list[dict]:
    key = _valid_stage_key(stage_key)
    comp = (component_type or "").strip()
    row = (
        db.query(ProductionStageRow)
        .filter(
            ProductionStageRow.award_id == award_id,
            ProductionStageRow.component_type == comp,
            ProductionStageRow.stage_key == key,
        )
        .first()
    )
    if row is None:
        return []
    return [
        {
            "id": att.id,
            "filename": att.filename,
            "content_type": att.content_type,
            "uploaded_at": att.uploaded_at,
        }
        for att in (row.attachments or [])
    ]


def attachment_counts_for_component(
    db: Session,
    award_id: int,
    component_type: str,
) -> dict[str, int]:
    rows = (
        db.query(ProductionStageRow)
        .filter(
            ProductionStageRow.award_id == award_id,
            ProductionStageRow.component_type == (component_type or "").strip(),
        )
        .all()
    )
    return {r.stage_key: len(r.attachments or []) for r in rows}


async def upload_attachment(
    db: Session,
    award_id: int,
    component_type: str,
    stage_key: str,
    file: UploadFile,
) -> dict:
    row = get_or_create_stage_row(db, award_id, component_type, stage_key)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    att = ProductionStageAttachment(
        stage_row_id=row.id,
        filename=(file.filename or "attachment.bin")[:500],
        content_type=(file.content_type or "application/octet-stream")[:200],
        data=data,
    )
    db.add(att)
    db.flush()
    return {
        "id": att.id,
        "filename": att.filename,
        "content_type": att.content_type,
        "uploaded_at": att.uploaded_at,
    }


def get_attachment_or_404(db: Session, attachment_id: int) -> ProductionStageAttachment:
    att = db.query(ProductionStageAttachment).filter(
        ProductionStageAttachment.id == attachment_id,
    ).first()
    if att is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return att


def delete_attachment(db: Session, attachment_id: int) -> None:
    att = get_attachment_or_404(db, attachment_id)
    db.delete(att)
