from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models.committee import CommitteeMember, MemberSigningRight, SigningRole
from schemas.committee import (
    CommitteeMemberCreate, CommitteeMemberUpdate, CommitteeMemberRead,
    MemberSigningRightCreate, MemberSigningRightRead,
)

router = APIRouter()


def _get_member_or_404(db: Session, member_id: int) -> CommitteeMember:
    obj = db.query(CommitteeMember).filter(CommitteeMember.id == member_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Committee member not found")
    return obj


def _member_read(obj: CommitteeMember) -> dict:
    data = CommitteeMemberRead.model_validate(obj).model_dump()
    data["has_photo"] = bool(obj.photo)
    return data


# ── CommitteeMember CRUD ────────────────────────────────────────────────────

@router.get("/", response_model=List[CommitteeMemberRead])
@router.get("", response_model=List[CommitteeMemberRead])
def list_members(is_active: Optional[bool] = None, db: Session = Depends(get_db)):
    q = db.query(CommitteeMember)
    if is_active is not None:
        q = q.filter(CommitteeMember.is_active == is_active)
    return [_member_read(m) for m in q.all()]


@router.post("/", response_model=CommitteeMemberRead, status_code=status.HTTP_201_CREATED)
def create_member(payload: CommitteeMemberCreate, db: Session = Depends(get_db)):
    obj = CommitteeMember(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _member_read(obj)


@router.get("/signers/by-award/{award_id}")
def list_signers_for_award(
    award_id: int,
    role: Optional[str] = Query("signer", description="signer | authorized"),
    db: Session = Depends(get_db),
):
    """Члены НК с правом подписи (или уполномоченные) по конкретной награде."""
    try:
        signing_role = SigningRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")
    rows = (
        db.query(CommitteeMember)
        .join(MemberSigningRight, MemberSigningRight.member_id == CommitteeMember.id)
        .filter(
            MemberSigningRight.award_id == award_id,
            MemberSigningRight.role == signing_role,
            CommitteeMember.is_active.is_(True),
        )
        .order_by(CommitteeMember.full_name)
        .all()
    )
    return [
        {
            "id": m.id,
            "full_name": m.full_name,
            "position": m.position,
            "organization": m.organization,
        }
        for m in rows
    ]


@router.get("/{member_id}", response_model=CommitteeMemberRead)
def get_member(member_id: int, db: Session = Depends(get_db)):
    return _member_read(_get_member_or_404(db, member_id))


@router.put("/{member_id}", response_model=CommitteeMemberRead)
def update_member(
    member_id: int, payload: CommitteeMemberUpdate, db: Session = Depends(get_db),
):
    obj = _get_member_or_404(db, member_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return _member_read(obj)


@router.post("/{member_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
async def upload_member_photo(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    obj = _get_member_or_404(db, member_id)
    obj.photo = await file.read()
    obj.photo_filename = file.filename or "photo.jpg"
    db.commit()


@router.get("/{member_id}/photo")
def download_member_photo(member_id: int, db: Session = Depends(get_db)):
    obj = _get_member_or_404(db, member_id)
    if not obj.photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    return Response(content=obj.photo, media_type="image/jpeg")


@router.delete("/{member_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_member_photo(member_id: int, db: Session = Depends(get_db)):
    obj = _get_member_or_404(db, member_id)
    obj.photo = None
    db.commit()


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: int, db: Session = Depends(get_db)):
    obj = _get_member_or_404(db, member_id)
    db.delete(obj)
    db.commit()


# ── Signing Rights ──────────────────────────────────────────────────────────

@router.post(
    "/{member_id}/signing-rights",
    response_model=MemberSigningRightRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_signing_right(
    member_id: int,
    payload: MemberSigningRightCreate,
    db: Session = Depends(get_db),
):
    _get_member_or_404(db, member_id)
    obj = MemberSigningRight(**payload.model_dump())
    obj.member_id = member_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{member_id}/signing-rights", response_model=List[MemberSigningRightRead])
def list_signing_rights(member_id: int, db: Session = Depends(get_db)):
    _get_member_or_404(db, member_id)
    return db.query(MemberSigningRight).filter(
        MemberSigningRight.member_id == member_id,
    ).all()


@router.delete("/signing-rights/{right_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_signing_right(right_id: int, db: Session = Depends(get_db)):
    obj = db.query(MemberSigningRight).filter(MemberSigningRight.id == right_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Signing right not found")
    db.delete(obj)
    db.commit()
