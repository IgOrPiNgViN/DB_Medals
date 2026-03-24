from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime,
    Boolean, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime


class SigningRole(str, enum.Enum):
    SIGNER = "signer"
    AUTHORIZED = "authorized"


class CommitteeMember(Base):
    __tablename__ = "committee_members"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(500), nullable=False)
    position = Column(String(500))
    organization = Column(String(500))
    phone = Column(String(100))
    email = Column(String(255))
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    signing_rights = relationship(
        "MemberSigningRight", back_populates="member", cascade="all, delete-orphan",
    )


class MemberSigningRight(Base):
    """Права подписи / уполномоченность члена НК по наградам"""
    __tablename__ = "member_signing_rights"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("committee_members.id"), nullable=False)
    award_id = Column(Integer, ForeignKey("awards.id"), nullable=False)
    role = Column(SAEnum(SigningRole), nullable=False)
    assigned_date = Column(Date)

    member = relationship("CommitteeMember", back_populates="signing_rights")
    award = relationship("Award")
