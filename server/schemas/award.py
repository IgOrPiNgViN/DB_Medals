from datetime import date, datetime

_Date = date  # алиас — поле named `date` с типом `date` конфликтует на Python 3.14 (PEP 649)
from typing import Optional, List

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
    has_image: bool = False
    has_image_back: bool = False
    has_establishment: bool = False
    has_development: bool = False

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
    has_protocol_data: Optional[bool] = False
    protocol_filename: Optional[str] = None


class AwardEstablishmentCreate(AwardEstablishmentBase):
    pass


class AwardEstablishmentRead(AwardEstablishmentBase):
    id: int
    has_protocol_file: bool = False

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


class AwardDetailRead(AwardRead):
    """Полная карточка награды: флаги наличия данных + вложенные блоки (если есть)."""

    establishment: Optional[AwardEstablishmentRead] = None
    development: Optional[AwardDevelopmentRead] = None

    model_config = ConfigDict(from_attributes=True)


# ── AwardApproval ────────────────────────────────────────────────────────────

class AwardApprovalBase(BaseModel):
    award_id: int
    approval_type: ApprovalType
    approver_name: Optional[str] = None
    status: Optional[str] = None
    date: Optional[_Date] = None
    details: Optional[str] = None


class AwardApprovalCreate(AwardApprovalBase):
    pass


class AwardApprovalRead(AwardApprovalBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class AwardApprovalUpdate(BaseModel):
    approval_type: Optional[ApprovalType] = None
    approver_name: Optional[str] = None
    status: Optional[str] = None
    date: Optional[_Date] = None
    details: Optional[str] = None


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


class AwardProductionUpdate(BaseModel):
    component_type: Optional[ComponentType] = None
    supplier: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[float] = None
    order_date: Optional[date] = None
    delivery_date: Optional[date] = None
    status: Optional[str] = None
    details: Optional[str] = None


# ── Production stages (ТЗ file-008) ─────────────────────────────────────────

class ProductionStageItem(BaseModel):
    stage_key: str
    label: Optional[str] = None
    status: Optional[str] = None
    stage_date: Optional[date] = None
    attachment_note: Optional[str] = None
    attachment_count: int = 0


class ProductionComponentStages(BaseModel):
    component_type: str
    is_ready: bool = False
    stages: List[ProductionStageItem] = []


class ProductionStagesResponse(BaseModel):
    components: List[ProductionComponentStages] = []


class ProductionStageUpdateItem(BaseModel):
    stage_key: str
    status: Optional[str] = None
    stage_date: Optional[date] = None
    attachment_note: Optional[str] = None


class ProductionComponentStagesUpdate(BaseModel):
    component_type: str
    is_ready: Optional[bool] = None
    stages: Optional[List[ProductionStageUpdateItem]] = None


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


class InventoryItemUpdate(BaseModel):
    """Частичное обновление строки склада (без award_id / component_type)."""

    total_count: Optional[int] = None
    reserve_count: Optional[int] = None
    issued_count: Optional[int] = None
    available_count: Optional[int] = None
    details: Optional[str] = None
