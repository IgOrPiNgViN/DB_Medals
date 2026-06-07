from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime,
    Boolean, Float, LargeBinary, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc)


class AwardType(str, enum.Enum):
    MEDAL = "medal"
    PPZ = "ppz"
    DISTINCTION = "distinction"
    DECORATION = "decoration"


class Award(Base):
    __tablename__ = "awards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)
    award_type = Column(SAEnum(AwardType), nullable=False)
    description = Column(Text)
    image_front = Column(LargeBinary)
    image_back = Column(LargeBinary)
    created_at = Column(DateTime, default=_utcnow)

    characteristics = relationship(
        "AwardCharacteristic", back_populates="award", cascade="all, delete-orphan",
    )
    establishment = relationship(
        "AwardEstablishment", back_populates="award",
        uselist=False, cascade="all, delete-orphan",
    )
    development = relationship(
        "AwardDevelopment", back_populates="award",
        uselist=False, cascade="all, delete-orphan",
    )
    approvals = relationship(
        "AwardApproval", back_populates="award", cascade="all, delete-orphan",
    )
    productions = relationship(
        "AwardProduction", back_populates="award", cascade="all, delete-orphan",
    )
    production_stage_rows = relationship(
        "ProductionStageRow", back_populates="award", cascade="all, delete-orphan",
    )
    production_component_ready = relationship(
        "ProductionComponentReady", back_populates="award", cascade="all, delete-orphan",
    )
    laureate_awards = relationship(
        "LaureateAward", back_populates="award", cascade="all, delete",
    )
    inventory_items = relationship(
        "InventoryItem", back_populates="award", cascade="all, delete-orphan",
    )
    kit_stock = relationship(
        "AwardKitStock", back_populates="award", uselist=False, cascade="all, delete-orphan",
    )
    decoration_disposals = relationship(
        "DecorationDisposal", back_populates="award", cascade="all, delete-orphan",
    )
    kit_disposals = relationship(
        "KitDisposal", back_populates="award", cascade="all, delete-orphan",
    )


class AwardCharacteristic(Base):
    __tablename__ = "award_characteristics"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    # Имена полей из Access (НаградыМега) бывают длинными
    field_name = Column(Text, nullable=False)
    field_value = Column(Text)

    award = relationship("Award", back_populates="characteristics")


class AwardEstablishment(Base):
    """Учреждение награды"""
    __tablename__ = "award_establishments"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False, unique=True)
    establishment_date = Column(Date)
    document_number = Column(String(100))
    document_date = Column(Date)
    initiator = Column(String(500))
    details = Column(Text)
    has_protocol_data = Column(Boolean, default=False)
    protocol_filename = Column(String(500))
    protocol_content_type = Column(String(200))
    protocol_data = Column(LargeBinary)

    award = relationship("Award", back_populates="establishment")


class AwardDevelopment(Base):
    """Разработка награды"""
    __tablename__ = "award_developments"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False, unique=True)
    developer = Column(String(500))
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(100))
    details = Column(Text)

    award = relationship("Award", back_populates="development")


class ApprovalType(str, enum.Enum):
    NK = "nk"
    HERALDISTS = "heraldists"
    RELATIVES = "relatives"
    SPONSORS = "sponsors"


class AwardApproval(Base):
    """Согласование награды"""
    __tablename__ = "award_approvals"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    approval_type = Column(SAEnum(ApprovalType), nullable=False)
    approver_name = Column(String(500))
    status = Column(String(100))
    date = Column(Date)
    details = Column(Text)

    award = relationship("Award", back_populates="approvals")


class ComponentType(str, enum.Enum):
    MEDAL = "medal"
    BADGE = "badge"
    CUFFLINKS = "cufflinks"
    PENDANT = "pendant"
    PPZ = "ppz"
    BOX = "box"
    CERTIFICATE = "certificate"
    CASE = "case"


class AwardProduction(Base):
    """Производство компонентов награды"""
    __tablename__ = "award_productions"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    component_type = Column(SAEnum(ComponentType), nullable=False)
    supplier = Column(String(500))
    quantity = Column(Integer, default=0)
    unit_price = Column(Float)
    order_date = Column(Date)
    delivery_date = Column(Date)
    status = Column(String(100))
    details = Column(Text)

    award = relationship("Award", back_populates="productions")


class ProductionStageRow(Base):
    """Этап производства компонента (статус / дата / вложение)."""
    __tablename__ = "production_stage_rows"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    component_type = Column(String(30), nullable=False)
    stage_key = Column(String(50), nullable=False)
    status = Column(String(200))
    stage_date = Column(Date)
    attachment_note = Column(String(500))

    award = relationship("Award", back_populates="production_stage_rows")
    attachments = relationship(
        "ProductionStageAttachment",
        back_populates="stage_row",
        cascade="all, delete-orphan",
    )


class ProductionStageAttachment(Base):
    """Файл вложения этапа производства (ТЗ file-008)."""
    __tablename__ = "production_stage_attachments"

    id = Column(Integer, primary_key=True, index=True)
    stage_row_id = Column(Integer, ForeignKey("production_stage_rows.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    content_type = Column(String(200))
    data = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime, default=_utcnow)

    stage_row = relationship("ProductionStageRow", back_populates="attachments")


class ProductionComponentReady(Base):
    """Флаг готовности компонента (ПРОИЗВ_*_чек)."""
    __tablename__ = "production_component_ready"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    component_type = Column(String(30), nullable=False)
    is_ready = Column(Boolean, nullable=False, default=False)

    award = relationship("Award", back_populates="production_component_ready")


class InventoryItem(Base):
    """Учёт (склад) — физический учёт комплектующих"""
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    component_type = Column(SAEnum(ComponentType), nullable=False)
    total_count = Column(Integer, default=0)
    reserve_count = Column(Integer, default=0)
    issued_count = Column(Integer, default=0)
    available_count = Column(Integer, default=0)
    details = Column(Text)
    updated_at = Column(DateTime, default=_utcnow, onupdate=datetime.utcnow)

    award = relationship("Award", back_populates="inventory_items")


class AwardKitStock(Base):
    """Собранные физические комплекты на складе."""
    __tablename__ = "award_kit_stock"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False, unique=True)
    physical_sets = Column(Integer, default=0)
    free_sets = Column(Integer, default=0)
    postponed_sets = Column(Integer, default=0)

    award = relationship("Award", back_populates="kit_stock")


class DecorationDisposal(Base):
    """Выбытие украшений (лауреатам или иное)."""
    __tablename__ = "decoration_disposals"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    laureate_award_id = Column(Integer, ForeignKey("laureate_awards.id"), nullable=True)
    component_type = Column(SAEnum(ComponentType), nullable=False)
    target = Column(String(20), nullable=False, default="laureate")
    event_name = Column(String(500))
    reason = Column(String(500))
    disposal_date = Column(Date)
    note = Column(Text)
    created_at = Column(DateTime, default=_utcnow)

    award = relationship("Award", back_populates="decoration_disposals")


class KitDisposal(Base):
    """Выбытие комплектов (лауреатам или иное — ТЗ file-012)."""
    __tablename__ = "kit_disposals"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    laureate_award_id = Column(Integer, ForeignKey("laureate_awards.id"), nullable=True)
    target = Column(String(20), nullable=False, default="laureate")
    event_name = Column(String(500))
    reason = Column(String(500))
    protocol_number = Column(String(100))
    disposal_date = Column(Date)
    note = Column(Text)
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=_utcnow)

    award = relationship("Award", back_populates="kit_disposals")


class UniversalStock(Base):
    """Общий склад универсальных удостоверений и коробок."""
    __tablename__ = "universal_stock"

    id = Column(Integer, primary_key=True, default=1)
    certificate_count = Column(Integer, default=0)
    box_count = Column(Integer, default=0)
