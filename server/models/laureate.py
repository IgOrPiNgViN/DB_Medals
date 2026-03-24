from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime,
    Boolean, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime


class LaureateCategory(str, enum.Enum):
    EMPLOYEE = "employee"
    VETERAN = "veteran"
    UNIVERSITY = "university"
    NII = "nii"
    NONPROFIT = "nonprofit"
    COMMERCIAL = "commercial"


class Laureate(Base):
    __tablename__ = "laureates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(500), nullable=False)
    category = Column(SAEnum(LaureateCategory))
    position = Column(String(500))
    organization = Column(String(500))
    phone = Column(String(100))
    email = Column(String(255))
    address = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    awards = relationship(
        "LaureateAward", back_populates="laureate", cascade="all, delete-orphan",
    )


class LaureateAward(Base):
    """Привязка лауреата к награде"""
    __tablename__ = "laureate_awards"

    id = Column(Integer, primary_key=True, index=True)
    laureate_id = Column(Integer, ForeignKey("laureates.id"), nullable=False)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    assigned_date = Column(Date)
    bulletin_number = Column(String(50))
    initiator = Column(String(500))
    status = Column(String(100), default="assigned")

    laureate = relationship("Laureate", back_populates="awards")
    award = relationship("Award", back_populates="laureate_awards")
    lifecycle = relationship(
        "LaureateLifecycle", back_populates="laureate_award",
        uselist=False, cascade="all, delete-orphan",
    )


class LifecycleStage(str, enum.Enum):
    NOMINATION = "nomination"
    VOTING = "voting"
    DECISION = "decision"
    REGISTRATION = "registration"
    AWARD_CEREMONY = "award_ceremony"
    PUBLICATION = "publication"


class LaureateLifecycle(Base):
    """Жизненный цикл лауреата"""
    __tablename__ = "laureate_lifecycles"

    id = Column(Integer, primary_key=True, index=True)
    laureate_award_id = Column(
        Integer, ForeignKey("laureate_awards.id"), nullable=False, unique=True,
    )

    nomination_date = Column(Date)
    nomination_initiator = Column(String(500))
    nomination_done = Column(Boolean, default=False)

    voting_date = Column(Date)
    voting_bulletin_number = Column(String(50))
    voting_done = Column(Boolean, default=False)

    decision_date = Column(Date)
    decision_protocol_number = Column(String(50))
    decision_done = Column(Boolean, default=False)

    registration_date = Column(Date)
    registration_signer_id = Column(Integer, ForeignKey("committee_members.id"))
    registration_certificate_number = Column(String(100))
    registration_done = Column(Boolean, default=False)

    ceremony_date = Column(Date)
    ceremony_place = Column(String(500))
    ceremony_done = Column(Boolean, default=False)

    publication_date = Column(Date)
    publication_source = Column(String(500))
    publication_done = Column(Boolean, default=False)

    inventory_reserved = Column(Boolean, default=False)
    inventory_issued = Column(Boolean, default=False)

    laureate_award = relationship("LaureateAward", back_populates="lifecycle")
    registration_signer = relationship(
        "CommitteeMember", foreign_keys=[registration_signer_id],
    )
