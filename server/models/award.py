from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime,
    Boolean, Float, LargeBinary, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime


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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    laureate_awards = relationship("LaureateAward", back_populates="award")
    inventory_items = relationship(
        "InventoryItem", back_populates="award", cascade="all, delete-orphan",
    )


class AwardCharacteristic(Base):
    __tablename__ = "award_characteristics"

    id = Column(Integer, primary_key=True, index=True)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    field_name = Column(String(255), nullable=False)
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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    award = relationship("Award", back_populates="inventory_items")
