from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.laureate import LaureateCategory, LifecycleStage


# ── Laureate ────────────────────────────────────────────────────────────────

class LaureateBase(BaseModel):
    full_name: str
    category: Optional[LaureateCategory] = None
    position: Optional[str] = None
    organization: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class LaureateCreate(LaureateBase):
    pass


class LaureateUpdate(BaseModel):
    full_name: Optional[str] = None
    category: Optional[LaureateCategory] = None
    position: Optional[str] = None
    organization: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class LaureateRead(LaureateBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── LaureateAward ───────────────────────────────────────────────────────────

class LaureateAwardBase(BaseModel):
    laureate_id: int
    award_id: int
    assigned_date: Optional[date] = None
    bulletin_number: Optional[str] = None
    initiator: Optional[str] = None
    status: Optional[str] = "assigned"


class LaureateAwardCreate(LaureateAwardBase):
    pass


class LaureateAwardRead(LaureateAwardBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── LaureateLifecycle ───────────────────────────────────────────────────────

class LaureateLifecycleBase(BaseModel):
    laureate_award_id: int
    nomination_date: Optional[date] = None
    nomination_initiator: Optional[str] = None
    nomination_done: Optional[bool] = False
    voting_date: Optional[date] = None
    voting_bulletin_number: Optional[str] = None
    voting_done: Optional[bool] = False
    decision_date: Optional[date] = None
    decision_protocol_number: Optional[str] = None
    decision_done: Optional[bool] = False
    registration_date: Optional[date] = None
    registration_signer_id: Optional[int] = None
    registration_certificate_number: Optional[str] = None
    registration_done: Optional[bool] = False
    ceremony_date: Optional[date] = None
    ceremony_place: Optional[str] = None
    ceremony_done: Optional[bool] = False
    publication_date: Optional[date] = None
    publication_source: Optional[str] = None
    publication_done: Optional[bool] = False
    inventory_reserved: Optional[bool] = False
    inventory_issued: Optional[bool] = False
    consent_sent_date: Optional[date] = None
    consent_received_date: Optional[date] = None
    consent_received: Optional[bool] = False


class LaureateLifecycleCreate(LaureateLifecycleBase):
    pass


class LaureateLifecycleUpdate(BaseModel):
    nomination_date: Optional[date] = None
    nomination_initiator: Optional[str] = None
    nomination_done: Optional[bool] = None
    voting_date: Optional[date] = None
    voting_bulletin_number: Optional[str] = None
    voting_done: Optional[bool] = None
    decision_date: Optional[date] = None
    decision_protocol_number: Optional[str] = None
    decision_done: Optional[bool] = None
    registration_date: Optional[date] = None
    registration_signer_id: Optional[int] = None
    registration_certificate_number: Optional[str] = None
    registration_done: Optional[bool] = None
    ceremony_date: Optional[date] = None
    ceremony_place: Optional[str] = None
    ceremony_done: Optional[bool] = None
    publication_date: Optional[date] = None
    publication_source: Optional[str] = None
    publication_done: Optional[bool] = None
    inventory_reserved: Optional[bool] = None
    inventory_issued: Optional[bool] = None
    consent_sent_date: Optional[date] = None
    consent_received_date: Optional[date] = None
    consent_received: Optional[bool] = None


class LaureateLifecycleRead(LaureateLifecycleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
