from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.committee import SigningRole


# ── CommitteeMember ─────────────────────────────────────────────────────────

class CommitteeMemberBase(BaseModel):
    full_name: str
    position: Optional[str] = None
    organization: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = True
    notes: Optional[str] = None


class CommitteeMemberCreate(CommitteeMemberBase):
    pass


class CommitteeMemberUpdate(BaseModel):
    full_name: Optional[str] = None
    position: Optional[str] = None
    organization: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class CommitteeMemberRead(CommitteeMemberBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── MemberSigningRight ──────────────────────────────────────────────────────

class MemberSigningRightBase(BaseModel):
    member_id: int
    award_id: int
    role: SigningRole
    assigned_date: Optional[date] = None


class MemberSigningRightCreate(MemberSigningRightBase):
    pass


class MemberSigningRightRead(MemberSigningRightBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
