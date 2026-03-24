from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime,
    Boolean, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime


class BulletinType(str, enum.Enum):
    MEDAL = "medal"
    PPZ = "ppz"


class BulletinStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class Bulletin(Base):
    __tablename__ = "bulletins"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(50), nullable=False, unique=True)
    bulletin_type = Column(SAEnum(BulletinType), nullable=False)
    voting_start = Column(Date)
    voting_end = Column(Date)
    postal_address = Column(Text)
    status = Column(SAEnum(BulletinStatus), default=BulletinStatus.DRAFT)
    created_at = Column(DateTime, default=datetime.utcnow)

    sections = relationship(
        "BulletinSection", back_populates="bulletin", cascade="all, delete-orphan",
    )
    distributions = relationship(
        "BulletinDistribution", back_populates="bulletin", cascade="all, delete-orphan",
    )
    protocol = relationship("Protocol", back_populates="bulletin", uselist=False)


class BulletinSection(Base):
    __tablename__ = "bulletin_sections"

    id = Column(Integer, primary_key=True, index=True)
    bulletin_id = Column(Integer, ForeignKey("bulletins.id"), nullable=False)
    section_name = Column(String(500), nullable=False)
    section_order = Column(Integer, default=0)

    bulletin = relationship("Bulletin", back_populates="sections")
    questions = relationship(
        "BulletinQuestion", back_populates="section", cascade="all, delete-orphan",
    )


class BulletinQuestion(Base):
    __tablename__ = "bulletin_questions"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("bulletin_sections.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_order = Column(Integer, default=0)
    laureate_award_id = Column(Integer, ForeignKey("laureate_awards.id"))
    initiator = Column(String(500))

    section = relationship("BulletinSection", back_populates="questions")
    laureate_award = relationship("LaureateAward")
    votes = relationship(
        "Vote", back_populates="question", cascade="all, delete-orphan",
    )


class BulletinDistribution(Base):
    """Рассылка бюллетеней членам НК"""
    __tablename__ = "bulletin_distributions"

    id = Column(Integer, primary_key=True, index=True)
    bulletin_id = Column(Integer, ForeignKey("bulletins.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("committee_members.id"), nullable=False)
    sent = Column(Boolean, default=False)
    sent_date = Column(Date)
    received = Column(Boolean, default=False)
    received_date = Column(Date)

    bulletin = relationship("Bulletin", back_populates="distributions")
    member = relationship("CommitteeMember")


class VoteValue(str, enum.Enum):
    FOR = "for"
    AGAINST = "against"


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("bulletin_questions.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("committee_members.id"), nullable=False)
    value = Column(SAEnum(VoteValue), default=VoteValue.FOR)
    voted_at = Column(DateTime, default=datetime.utcnow)

    question = relationship("BulletinQuestion", back_populates="votes")
    member = relationship("CommitteeMember")


class ProtocolStatus(str, enum.Enum):
    DRAFT = "draft"
    SIGNED = "signed"


class Protocol(Base):
    __tablename__ = "protocols"

    id = Column(Integer, primary_key=True, index=True)
    bulletin_id = Column(Integer, ForeignKey("bulletins.id"), nullable=False, unique=True)
    number = Column(String(50), nullable=False)
    date = Column(Date)
    status = Column(SAEnum(ProtocolStatus), default=ProtocolStatus.DRAFT)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    bulletin = relationship("Bulletin", back_populates="protocol")
    extracts = relationship(
        "ProtocolExtract", back_populates="protocol", cascade="all, delete-orphan",
    )


class ProtocolExtract(Base):
    """Выписка из протокола"""
    __tablename__ = "protocol_extracts"

    id = Column(Integer, primary_key=True, index=True)
    protocol_id = Column(Integer, ForeignKey("protocols.id"), nullable=False)
    laureate_award_id = Column(Integer, ForeignKey("laureate_awards.id"), nullable=False)
    extract_date = Column(Date)
    details = Column(Text)

    protocol = relationship("Protocol", back_populates="extracts")
    laureate_award = relationship("LaureateAward")


class PPZSubmission(Base):
    """Представление на награждение ППЗ"""
    __tablename__ = "ppz_submissions"

    id = Column(Integer, primary_key=True, index=True)
    laureate_award_id = Column(Integer, ForeignKey("laureate_awards.id"), nullable=False)
    authorized_member_id = Column(
        Integer, ForeignKey("committee_members.id"), nullable=False,
    )
    submission_number = Column(String(50))
    date = Column(Date)
    details = Column(Text)

    laureate_award = relationship("LaureateAward")
    authorized_member = relationship("CommitteeMember")
