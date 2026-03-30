from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List

from database import get_db
from models.voting import (
    Bulletin, BulletinSection, BulletinQuestion,
    BulletinDistribution, Vote, Protocol, ProtocolExtract, PPZSubmission,
)
from models.committee import CommitteeMember
from schemas.voting import (
    BulletinCreate, BulletinUpdate, BulletinRead,
    BulletinSectionCreate, BulletinSectionRead,
    BulletinQuestionCreate, BulletinQuestionRead,
    BulletinDistributionUpdate, BulletinDistributionRead,
    VoteCreate, VoteRead,
    ProtocolCreate, ProtocolUpdate, ProtocolRead,
    ProtocolExtractCreate, ProtocolExtractRead,
    PPZSubmissionCreate, PPZSubmissionRead,
    DistributeRequest, QuestionResult, MonitoringEntry,
)

router = APIRouter()


# ── helpers ─────────────────────────────────────────────────────────────────

def _get_bulletin_or_404(db: Session, bulletin_id: int) -> Bulletin:
    obj = db.query(Bulletin).filter(Bulletin.id == bulletin_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Bulletin not found")
    return obj


def _get_section_or_404(db: Session, section_id: int) -> BulletinSection:
    obj = db.query(BulletinSection).filter(BulletinSection.id == section_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Section not found")
    return obj


def _get_question_or_404(db: Session, question_id: int) -> BulletinQuestion:
    obj = db.query(BulletinQuestion).filter(BulletinQuestion.id == question_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Question not found")
    return obj


# ── Bulletin CRUD ───────────────────────────────────────────────────────────

@router.get("/bulletins", response_model=List[BulletinRead])
def list_bulletins(db: Session = Depends(get_db)):
    return db.query(Bulletin).all()


@router.post("/bulletins", response_model=BulletinRead, status_code=status.HTTP_201_CREATED)
def create_bulletin(payload: BulletinCreate, db: Session = Depends(get_db)):
    obj = Bulletin(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/bulletins/{bulletin_id}", response_model=BulletinRead)
def get_bulletin(bulletin_id: int, db: Session = Depends(get_db)):
    return _get_bulletin_or_404(db, bulletin_id)


@router.get("/bulletins/{bulletin_id}/full")
def get_bulletin_full(bulletin_id: int, db: Session = Depends(get_db)):
    """Бюллетень с разделами и вопросами (для клиента: формирование документа, голосование)."""
    b = (
        db.query(Bulletin)
        .options(
            joinedload(Bulletin.sections).joinedload(BulletinSection.questions),
        )
        .filter(Bulletin.id == bulletin_id)
        .first()
    )
    if not b:
        raise HTTPException(status_code=404, detail="Bulletin not found")

    def _sections():
        for s in sorted(b.sections, key=lambda x: (x.section_order or 0, x.id)):
            qs = sorted(s.questions, key=lambda q: (q.question_order or 0, q.id))
            yield {
                "id": s.id,
                "section_name": s.section_name,
                "section_order": s.section_order,
                "questions": [
                    {
                        "id": q.id,
                        "question_text": q.question_text,
                        "question_order": q.question_order,
                        "initiator": q.initiator,
                        "laureate_award_id": q.laureate_award_id,
                    }
                    for q in qs
                ],
            }

    return {
        "id": b.id,
        "number": b.number,
        "bulletin_type": b.bulletin_type.value if b.bulletin_type else None,
        "voting_start": b.voting_start,
        "voting_end": b.voting_end,
        "postal_address": b.postal_address,
        "status": b.status.value if b.status else None,
        "sections": list(_sections()),
    }


@router.put("/bulletins/{bulletin_id}", response_model=BulletinRead)
def update_bulletin(
    bulletin_id: int, payload: BulletinUpdate, db: Session = Depends(get_db),
):
    obj = _get_bulletin_or_404(db, bulletin_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/bulletins/{bulletin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bulletin(bulletin_id: int, db: Session = Depends(get_db)):
    obj = _get_bulletin_or_404(db, bulletin_id)
    db.delete(obj)
    db.commit()


# ── Sections ────────────────────────────────────────────────────────────────

@router.post(
    "/bulletins/{bulletin_id}/sections",
    response_model=BulletinSectionRead,
    status_code=status.HTTP_201_CREATED,
)
def add_section(
    bulletin_id: int, payload: BulletinSectionCreate, db: Session = Depends(get_db),
):
    _get_bulletin_or_404(db, bulletin_id)
    obj = BulletinSection(**payload.model_dump())
    obj.bulletin_id = bulletin_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── Questions ───────────────────────────────────────────────────────────────

@router.post(
    "/sections/{section_id}/questions",
    response_model=BulletinQuestionRead,
    status_code=status.HTTP_201_CREATED,
)
def add_question(
    section_id: int, payload: BulletinQuestionCreate, db: Session = Depends(get_db),
):
    _get_section_or_404(db, section_id)
    obj = BulletinQuestion(**payload.model_dump())
    obj.section_id = section_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── Distribution ────────────────────────────────────────────────────────────

@router.post(
    "/bulletins/{bulletin_id}/distribute",
    response_model=List[BulletinDistributionRead],
    status_code=status.HTTP_201_CREATED,
)
def distribute_bulletin(
    bulletin_id: int, payload: DistributeRequest, db: Session = Depends(get_db),
):
    _get_bulletin_or_404(db, bulletin_id)
    created = []
    for member_id in payload.member_ids:
        member = db.query(CommitteeMember).filter(
            CommitteeMember.id == member_id,
        ).first()
        if not member:
            raise HTTPException(
                status_code=404,
                detail=f"Committee member {member_id} not found",
            )
        dist = BulletinDistribution(
            bulletin_id=bulletin_id,
            member_id=member_id,
        )
        db.add(dist)
        created.append(dist)
    db.commit()
    for d in created:
        db.refresh(d)
    return created


@router.put("/distributions/{distribution_id}", response_model=BulletinDistributionRead)
def update_distribution(
    distribution_id: int,
    payload: BulletinDistributionUpdate,
    db: Session = Depends(get_db),
):
    obj = db.query(BulletinDistribution).filter(
        BulletinDistribution.id == distribution_id,
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Distribution not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/bulletins/{bulletin_id}/monitoring", response_model=List[MonitoringEntry])
def monitoring(bulletin_id: int, db: Session = Depends(get_db)):
    _get_bulletin_or_404(db, bulletin_id)
    dists = (
        db.query(BulletinDistribution)
        .options(joinedload(BulletinDistribution.member))
        .filter(BulletinDistribution.bulletin_id == bulletin_id)
        .all()
    )
    return [
        MonitoringEntry(
            member_id=d.member_id,
            member_name=d.member.full_name,
            sent=d.sent or False,
            sent_date=d.sent_date,
            received=d.received or False,
            received_date=d.received_date,
        )
        for d in dists
    ]


# ── Votes ───────────────────────────────────────────────────────────────────

@router.post(
    "/questions/{question_id}/votes",
    response_model=VoteRead,
    status_code=status.HTTP_201_CREATED,
)
def record_vote(
    question_id: int, payload: VoteCreate, db: Session = Depends(get_db),
):
    _get_question_or_404(db, question_id)
    obj = Vote(**payload.model_dump())
    obj.question_id = question_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/bulletins/{bulletin_id}/results", response_model=List[QuestionResult])
def vote_results(bulletin_id: int, db: Session = Depends(get_db)):
    """Подсчёт голосов по каждому вопросу бюллетеня (порог 65 %)."""
    bulletin = _get_bulletin_or_404(db, bulletin_id)
    sections = (
        db.query(BulletinSection)
        .filter(BulletinSection.bulletin_id == bulletin_id)
        .all()
    )
    section_ids = [s.id for s in sections]
    if not section_ids:
        return []

    questions = (
        db.query(BulletinQuestion)
        .options(joinedload(BulletinQuestion.votes))
        .filter(BulletinQuestion.section_id.in_(section_ids))
        .all()
    )

    results = []
    for q in questions:
        total = len(q.votes)
        votes_for = sum(1 for v in q.votes if v.value.value == "for")
        votes_against = total - votes_for
        pct = (votes_for / total * 100) if total > 0 else 0.0
        results.append(
            QuestionResult(
                question_id=q.id,
                question_text=q.question_text,
                total_votes=total,
                votes_for=votes_for,
                votes_against=votes_against,
                percent_for=round(pct, 2),
                passed=pct >= 65.0,
            )
        )
    return results


# ── Protocol ────────────────────────────────────────────────────────────────

@router.post(
    "/bulletins/{bulletin_id}/protocol",
    response_model=ProtocolRead,
    status_code=status.HTTP_201_CREATED,
)
def create_protocol(
    bulletin_id: int, payload: ProtocolCreate, db: Session = Depends(get_db),
):
    _get_bulletin_or_404(db, bulletin_id)
    existing = db.query(Protocol).filter(Protocol.bulletin_id == bulletin_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Protocol already exists for this bulletin")
    obj = Protocol(**payload.model_dump())
    obj.bulletin_id = bulletin_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/protocols", response_model=List[ProtocolRead])
def list_protocols(db: Session = Depends(get_db)):
    return db.query(Protocol).all()


@router.put("/protocols/{protocol_id}", response_model=ProtocolRead)
def update_protocol(
    protocol_id: int, payload: ProtocolUpdate, db: Session = Depends(get_db),
):
    obj = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Protocol not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


# ── Protocol Extracts ───────────────────────────────────────────────────────

@router.post(
    "/protocols/{protocol_id}/extracts",
    response_model=ProtocolExtractRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract(
    protocol_id: int, payload: ProtocolExtractCreate, db: Session = Depends(get_db),
):
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")
    obj = ProtocolExtract(**payload.model_dump())
    obj.protocol_id = protocol_id
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


# ── PPZ Submissions ─────────────────────────────────────────────────────────

@router.post(
    "/ppz-submissions",
    response_model=PPZSubmissionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ppz_submission(payload: PPZSubmissionCreate, db: Session = Depends(get_db)):
    obj = PPZSubmission(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
