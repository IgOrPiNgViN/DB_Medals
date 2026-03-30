from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models.committee import CommitteeMember, MemberSigningRight
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


# ── CommitteeMember CRUD ────────────────────────────────────────────────────

@router.get("/", response_model=List[CommitteeMemberRead])
@router.get("", response_model=List[CommitteeMemberRead])
def list_members(is_active: Optional[bool] = None, db: Session = Depends(get_db)):
    q = db.query(CommitteeMember)
    if is_active is not None:
        q = q.filter(CommitteeMember.is_active == is_active)
    return q.all()


@router.post("/", response_model=CommitteeMemberRead, status_code=status.HTTP_201_CREATED)
def create_member(payload: CommitteeMemberCreate, db: Session = Depends(get_db)):
    obj = CommitteeMember(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{member_id}", response_model=CommitteeMemberRead)
def get_member(member_id: int, db: Session = Depends(get_db)):
    return _get_member_or_404(db, member_id)


@router.put("/{member_id}", response_model=CommitteeMemberRead)
def update_member(
    member_id: int, payload: CommitteeMemberUpdate, db: Session = Depends(get_db),
):
    obj = _get_member_or_404(db, member_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


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
