from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from models.voting import BulletinType, BulletinStatus, VoteValue, ProtocolStatus


# ── Bulletin ────────────────────────────────────────────────────────────────

class BulletinBase(BaseModel):
    number: str
    bulletin_type: BulletinType
    voting_start: Optional[date] = None
    voting_end: Optional[date] = None
    postal_address: Optional[str] = None
    status: Optional[BulletinStatus] = BulletinStatus.DRAFT


class BulletinCreate(BulletinBase):
    pass


class BulletinUpdate(BaseModel):
    number: Optional[str] = None
    bulletin_type: Optional[BulletinType] = None
    voting_start: Optional[date] = None
    voting_end: Optional[date] = None
    postal_address: Optional[str] = None
    status: Optional[BulletinStatus] = None


class BulletinRead(BulletinBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── BulletinSection ─────────────────────────────────────────────────────────

class BulletinSectionBase(BaseModel):
    bulletin_id: int
    section_name: str
    section_order: Optional[int] = 0


class BulletinSectionCreate(BulletinSectionBase):
    pass


class BulletinSectionRead(BulletinSectionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── BulletinQuestion ────────────────────────────────────────────────────────

class BulletinQuestionBase(BaseModel):
    section_id: int
    question_text: str
    question_order: Optional[int] = 0
    laureate_award_id: Optional[int] = None
    initiator: Optional[str] = None


class BulletinQuestionCreate(BulletinQuestionBase):
    pass


class BulletinQuestionRead(BulletinQuestionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── BulletinDistribution ───────────────────────────────────────────────────

class BulletinDistributionBase(BaseModel):
    bulletin_id: int
    member_id: int
    sent: Optional[bool] = False
    sent_date: Optional[date] = None
    received: Optional[bool] = False
    received_date: Optional[date] = None


class BulletinDistributionCreate(BulletinDistributionBase):
    pass


class BulletinDistributionUpdate(BaseModel):
    sent: Optional[bool] = None
    sent_date: Optional[date] = None
    received: Optional[bool] = None
    received_date: Optional[date] = None


class BulletinDistributionRead(BulletinDistributionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── Vote ────────────────────────────────────────────────────────────────────

class VoteBase(BaseModel):
    question_id: int
    member_id: int
    value: Optional[VoteValue] = VoteValue.FOR


class VoteCreate(VoteBase):
    pass


class VoteRead(VoteBase):
    id: int
    voted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Protocol ────────────────────────────────────────────────────────────────

class ProtocolBase(BaseModel):
    bulletin_id: int
    number: str
    date: Optional[date] = None
    status: Optional[ProtocolStatus] = ProtocolStatus.DRAFT
    details: Optional[str] = None


class ProtocolCreate(ProtocolBase):
    pass


class ProtocolUpdate(BaseModel):
    number: Optional[str] = None
    date: Optional[date] = None
    status: Optional[ProtocolStatus] = None
    details: Optional[str] = None


class ProtocolRead(ProtocolBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── ProtocolExtract ─────────────────────────────────────────────────────────

class ProtocolExtractBase(BaseModel):
    protocol_id: int
    laureate_award_id: int
    extract_date: Optional[date] = None
    details: Optional[str] = None


class ProtocolExtractCreate(ProtocolExtractBase):
    pass


class ProtocolExtractRead(ProtocolExtractBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── PPZSubmission ───────────────────────────────────────────────────────────

class PPZSubmissionBase(BaseModel):
    laureate_award_id: int
    authorized_member_id: int
    submission_number: Optional[str] = None
    date: Optional[date] = None
    details: Optional[str] = None


class PPZSubmissionCreate(PPZSubmissionBase):
    pass


class PPZSubmissionRead(PPZSubmissionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── Distribute request ──────────────────────────────────────────────────────

class DistributeRequest(BaseModel):
    member_ids: List[int]


# ── Vote result (response-only) ────────────────────────────────────────────

class QuestionResult(BaseModel):
    question_id: int
    question_text: str
    total_votes: int
    votes_for: int
    votes_against: int
    percent_for: float
    passed: bool


class MonitoringEntry(BaseModel):
    member_id: int
    member_name: str
    sent: bool
    sent_date: Optional[date] = None
    received: bool
    received_date: Optional[date] = None
