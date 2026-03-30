from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.award import AwardType, ApprovalType, ComponentType


# ── Award ────────────────────────────────────────────────────────────────────

class AwardBase(BaseModel):
    name: str
    award_type: AwardType
    description: Optional[str] = None


class AwardCreate(AwardBase):
    pass


class AwardUpdate(BaseModel):
    name: Optional[str] = None
    award_type: Optional[AwardType] = None
    description: Optional[str] = None


class AwardRead(AwardBase):
    id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AwardListItem(BaseModel):
    """Элемент списка наград (без бинарных полей) + признак наличия изображения."""

    id: int
    name: str
    award_type: AwardType
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    has_image: bool = False
    has_image_back: bool = False

    model_config = ConfigDict(from_attributes=True)


# ── AwardCharacteristic ─────────────────────────────────────────────────────

class AwardCharacteristicBase(BaseModel):
    award_id: int
    field_name: str
    field_value: Optional[str] = None


class AwardCharacteristicCreate(AwardCharacteristicBase):
    pass


class AwardCharacteristicRead(AwardCharacteristicBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── AwardEstablishment ───────────────────────────────────────────────────────

class AwardEstablishmentBase(BaseModel):
    award_id: int
    establishment_date: Optional[date] = None
    document_number: Optional[str] = None
    document_date: Optional[date] = None
    initiator: Optional[str] = None
    details: Optional[str] = None


class AwardEstablishmentCreate(AwardEstablishmentBase):
    pass


class AwardEstablishmentRead(AwardEstablishmentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── AwardDevelopment ─────────────────────────────────────────────────────────

class AwardDevelopmentBase(BaseModel):
    award_id: int
    developer: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    details: Optional[str] = None


class AwardDevelopmentCreate(AwardDevelopmentBase):
    pass


class AwardDevelopmentRead(AwardDevelopmentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── AwardApproval ────────────────────────────────────────────────────────────

class AwardApprovalBase(BaseModel):
    award_id: int
    approval_type: ApprovalType
    approver_name: Optional[str] = None
    status: Optional[str] = None
    date: Optional[date] = None
    details: Optional[str] = None


class AwardApprovalCreate(AwardApprovalBase):
    pass


class AwardApprovalRead(AwardApprovalBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── AwardProduction ──────────────────────────────────────────────────────────

class AwardProductionBase(BaseModel):
    award_id: int
    component_type: ComponentType
    supplier: Optional[str] = None
    quantity: Optional[int] = 0
    unit_price: Optional[float] = None
    order_date: Optional[date] = None
    delivery_date: Optional[date] = None
    status: Optional[str] = None
    details: Optional[str] = None


class AwardProductionCreate(AwardProductionBase):
    pass


class AwardProductionRead(AwardProductionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ── InventoryItem ────────────────────────────────────────────────────────────

class InventoryItemBase(BaseModel):
    award_id: int
    component_type: ComponentType
    total_count: Optional[int] = 0
    reserve_count: Optional[int] = 0
    issued_count: Optional[int] = 0
    available_count: Optional[int] = 0
    details: Optional[str] = None


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemRead(InventoryItemBase):
    id: int
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
