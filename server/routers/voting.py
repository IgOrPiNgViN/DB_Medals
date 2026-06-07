from datetime import date as dt_date
import math
import re
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from typing import List
from docx import Document

from database import get_db
from config import (
    BULLETIN_TEMPLATE_PATH,
    PROTOCOL_BRIEF_TEMPLATE_PATH,
    PROTOCOL_FULL_TEMPLATE_PATH,
    EXTRACT_MEDAL_TEMPLATE_PATH,
    EXTRACT_PPZ_TEMPLATE_PATH,
    PPZ_SUBMISSION_TEMPLATE_PATH,
    MONITORING_TEMPLATE_PATH,
)
from services.docx_templates import render_template
from models.voting import (
    Bulletin, BulletinSection, BulletinQuestion,
    BulletinDistribution, Vote, Protocol, ProtocolExtract, PPZSubmission,
)
from models.committee import CommitteeMember
from models.laureate import LaureateAward
from schemas.voting import (
    BulletinCreate, BulletinUpdate, BulletinRead,
    BulletinSectionCreate, BulletinSectionRead,
    BulletinQuestionCreate, BulletinQuestionRead,
    BulletinDistributionUpdate, BulletinDistributionRead, BulletinDistributionMemberRead,
    VoteCreate, VoteRead,
    ProtocolCreate, ProtocolUpdate, ProtocolRead,
    ProtocolExtractCreate, ProtocolExtractRead,
    PPZSubmissionCreate, PPZSubmissionRead,
    DistributeRequest, QuestionResult, MonitoringEntry, MonitoringSummary,
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


def _safe_filename(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]+", "_", s or "").strip()
    return s or "document"


def _content_disposition(filename: str) -> str:
    """RFC 5987 — поддержка кириллицы в заголовке Content-Disposition."""
    encoded = quote(filename, safe="")
    return f"attachment; filename*=UTF-8''{encoded}"


def _docx_response(doc: Document, filename: str) -> Response:
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    headers = {"Content-Disposition": _content_disposition(filename)}
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


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


@router.get("/bulletins/{bulletin_id}/docx")
def bulletin_docx(bulletin_id: int, db: Session = Depends(get_db)):
    """DOCX-версия бюллетеня по организационному шаблону."""
    b = (
        db.query(Bulletin)
        .options(joinedload(Bulletin.sections).joinedload(BulletinSection.questions))
        .filter(Bulletin.id == bulletin_id)
        .first()
    )
    if not b:
        raise HTTPException(status_code=404, detail="Bulletin not found")

    lines: list[str] = []
    sections = sorted(b.sections, key=lambda x: (x.section_order or 0, x.id))
    for s in sections:
        lines.append(str(s.section_name or ""))
        questions = sorted(s.questions, key=lambda q: (q.question_order or 0, q.id))
        for idx, q in enumerate(questions, 1):
            lines.append(f"{idx}. {q.question_text}")
    questions_text = "\n".join(lines) if lines else "Вопросы не добавлены."

    mapping = {
        "BULLETIN_NUMBER": str(b.number),
        "BULLETIN_TYPE": b.bulletin_type.value if b.bulletin_type else "—",
        "VOTING_START": str(b.voting_start or "—"),
        "VOTING_END": str(b.voting_end or "—"),
        "ADDRESS": str(b.postal_address or "—"),
        "QUESTIONS": questions_text,
    }
    content = render_template(BULLETIN_TEMPLATE_PATH, "Бюллетень", mapping)
    filename = f"Бюллетень_{_safe_filename(str(b.number))}.docx"
    headers = {"Content-Disposition": _content_disposition(filename)}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


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
    protocol = db.query(Protocol).filter(Protocol.bulletin_id == bulletin_id).first()
    if protocol is not None:
        db.delete(protocol)
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


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(question_id: int, db: Session = Depends(get_db)):
    obj = _get_question_or_404(db, question_id)
    db.delete(obj)
    db.commit()


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
        dist = db.query(BulletinDistribution).filter(
            BulletinDistribution.bulletin_id == bulletin_id,
            BulletinDistribution.member_id == member_id,
        ).first()
        if dist is None:
            dist = BulletinDistribution(bulletin_id=bulletin_id, member_id=member_id)
            db.add(dist)
        # «Рассылка» = пометить как отправлено сегодня (упрощённая модель ТЗ)
        dist.sent = True
        dist.sent_date = dt_date.today()
        created.append(dist)
    db.commit()
    for d in created:
        db.refresh(d)
    return created


@router.get(
    "/bulletins/{bulletin_id}/distributions",
    response_model=List[BulletinDistributionMemberRead],
)
def list_bulletin_distributions(bulletin_id: int, db: Session = Depends(get_db)):
    """Список рассылки бюллетеня с e-mail членов НК."""
    _get_bulletin_or_404(db, bulletin_id)
    dists = (
        db.query(BulletinDistribution)
        .options(joinedload(BulletinDistribution.member))
        .filter(BulletinDistribution.bulletin_id == bulletin_id)
        .order_by(BulletinDistribution.id)
        .all()
    )
    out = []
    for d in dists:
        item = BulletinDistributionRead.model_validate(d).model_dump()
        item["member_name"] = d.member.full_name if d.member else None
        item["member_email"] = d.member.email if d.member else None
        out.append(item)
    return out


@router.get("/bulletins/{bulletin_id}/distributions.csv")
def export_distributions_csv(bulletin_id: int, db: Session = Depends(get_db)):
    """
    Экспорт рассылки бюллетеня для внешней отправки/контроля (упрощённо вместо Excel).
    """
    _get_bulletin_or_404(db, bulletin_id)
    dists = (
        db.query(BulletinDistribution)
        .options(joinedload(BulletinDistribution.member))
        .filter(BulletinDistribution.bulletin_id == bulletin_id)
        .all()
    )

    def esc(v) -> str:
        s = "" if v is None else str(v)
        s = s.replace('"', '""')
        return f'"{s}"'

    lines = [
        "member_id,member_name,sent,sent_date,received,received_date",
    ]
    for d in dists:
        lines.append(",".join([
            esc(d.member_id),
            esc(d.member.full_name if d.member else ""),
            esc(bool(d.sent)),
            esc(d.sent_date.isoformat() if d.sent_date else ""),
            esc(bool(d.received)),
            esc(d.received_date.isoformat() if d.received_date else ""),
        ]))

    content = ("\n".join(lines) + "\n").encode("utf-8")
    headers = {"Content-Disposition": f'attachment; filename="bulletin_{bulletin_id}_distributions.csv"'}
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/bulletins/{bulletin_id}/distributions.xlsx")
def export_distributions_xlsx(bulletin_id: int, db: Session = Depends(get_db)):
    """
    Экспорт рассылки бюллетеня в XLSX.
    """
    _get_bulletin_or_404(db, bulletin_id)
    dists = (
        db.query(BulletinDistribution)
        .options(joinedload(BulletinDistribution.member))
        .filter(BulletinDistribution.bulletin_id == bulletin_id)
        .all()
    )

    try:
        from openpyxl import Workbook
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"openpyxl is not installed: {e}")

    wb = Workbook()
    ws = wb.active
    ws.title = "Distributions"
    ws.append(["member_id", "member_name", "sent", "sent_date", "received", "received_date"])
    for d in dists:
        ws.append([
            d.member_id,
            d.member.full_name if d.member else "",
            bool(d.sent),
            d.sent_date.isoformat() if d.sent_date else "",
            bool(d.received),
            d.received_date.isoformat() if d.received_date else "",
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="bulletin_{bulletin_id}_distributions.xlsx"'}
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


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


VOTING_QUORUM_RATIO = 0.65


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
            distribution_id=d.id,
            member_id=d.member_id,
            member_name=d.member.full_name if d.member else "",
            sent=d.sent or False,
            sent_date=d.sent_date,
            received=d.received or False,
            received_date=d.received_date,
        )
        for d in dists
    ]


@router.get("/bulletins/{bulletin_id}/monitoring-summary", response_model=MonitoringSummary)
def monitoring_summary(bulletin_id: int, db: Session = Depends(get_db)):
    """Мониторинг с кворумом 65 % действующих членов НК."""
    _get_bulletin_or_404(db, bulletin_id)
    dists = (
        db.query(BulletinDistribution)
        .options(joinedload(BulletinDistribution.member))
        .filter(BulletinDistribution.bulletin_id == bulletin_id)
        .all()
    )
    active = db.query(CommitteeMember).filter(CommitteeMember.is_active.is_(True)).count()
    required = max(1, math.ceil(active * VOTING_QUORUM_RATIO)) if active else 1
    received = sum(1 for d in dists if d.received)
    entries = [
        MonitoringEntry(
            distribution_id=d.id,
            member_id=d.member_id,
            member_name=d.member.full_name if d.member else "",
            sent=d.sent or False,
            sent_date=d.sent_date,
            received=d.received or False,
            received_date=d.received_date,
        )
        for d in dists
    ]
    return MonitoringSummary(
        active_members=active,
        required_received=required,
        received_count=received,
        distributed_count=len(dists),
        quorum_met=received >= required and len(dists) > 0,
        entries=entries,
    )


@router.get("/bulletins/{bulletin_id}/monitoring.docx")
def monitoring_docx(bulletin_id: int, db: Session = Depends(get_db)):
    """DOCX-отчёт мониторинга ответов НК."""
    bulletin = _get_bulletin_or_404(db, bulletin_id)
    summary = monitoring_summary(bulletin_id, db)
    lines = []
    for e in summary.entries:
        st = "получен" if e.received else ("отправлен" if e.sent else "не отправлен")
        lines.append(f"{e.member_name}: {st}")
    mapping = {
        "BULLETIN_NUMBER": str(bulletin.number),
        "REQUIRED": str(summary.required_received),
        "RECEIVED": str(summary.received_count),
        "MEMBERS_TABLE": "\n".join(lines) if lines else "—",
    }
    content = render_template(MONITORING_TEMPLATE_PATH, "Мониторинг", mapping)
    filename = f"Мониторинг_Б{_safe_filename(str(bulletin.number))}.docx"
    headers = {"Content-Disposition": _content_disposition(filename)}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


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
    existing = db.query(Vote).filter(
        Vote.question_id == question_id,
        Vote.member_id == payload.member_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already voted for this question",
        )
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
        votes_for = sum(1 for v in q.votes if v.value is not None and v.value.value == "for")
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


@router.delete("/protocols/{protocol_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_protocol(protocol_id: int, db: Session = Depends(get_db)):
    obj = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Protocol not found")
    db.delete(obj)
    db.commit()


@router.get("/protocols/{protocol_id}/docx")
def protocol_docx(
    protocol_id: int,
    variant: str = Query("full", pattern="^(brief|full)$"),
    db: Session = Depends(get_db),
):
    """DOCX-версия протокола (краткий или подробный шаблон)."""
    p = (
        db.query(Protocol)
        .options(joinedload(Protocol.bulletin))
        .filter(Protocol.id == protocol_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Protocol not found")

    results = vote_results(p.bulletin_id, db)
    summary_lines = [
        f"{r.question_text}: {r.percent_for:.1f}% ({'принято' if r.passed else 'не принято'})"
        for r in results
    ]
    table_lines = [
        f"{r.question_text} | за: {r.votes_for} | против: {r.votes_against} | {r.percent_for:.1f}%"
        for r in results
    ]
    mapping = {
        "PROTOCOL_NUMBER": str(p.number),
        "PROTOCOL_DATE": str(p.date or "—"),
        "BULLETIN_NUMBER": str(p.bulletin.number if p.bulletin else p.bulletin_id),
        "STATUS": p.status.value if p.status else "—",
        "DETAILS": p.details or "—",
        "RESULTS_SUMMARY": "\n".join(summary_lines) if summary_lines else "Нет данных",
        "RESULTS_TABLE": "\n".join(table_lines) if table_lines else "Нет данных",
    }
    path = PROTOCOL_BRIEF_TEMPLATE_PATH if variant == "brief" else PROTOCOL_FULL_TEMPLATE_PATH
    label = "Протокол (краткий)" if variant == "brief" else "Протокол (подробный)"
    content = render_template(path, label, mapping)
    suffix = "краткий" if variant == "brief" else "подробный"
    filename = f"Протокол_{_safe_filename(str(p.number))}_{suffix}.docx"
    headers = {"Content-Disposition": _content_disposition(filename)}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


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


@router.get("/extracts", response_model=List[ProtocolExtractRead])
def list_extracts(db: Session = Depends(get_db)):
    return db.query(ProtocolExtract).all()


@router.delete("/extracts/{extract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_extract(extract_id: int, db: Session = Depends(get_db)):
    obj = db.query(ProtocolExtract).filter(ProtocolExtract.id == extract_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Extract not found")
    db.delete(obj)
    db.commit()


@router.get("/extracts/{extract_id}/docx")
def extract_docx(extract_id: int, db: Session = Depends(get_db)):
    e = (
        db.query(ProtocolExtract)
        .options(joinedload(ProtocolExtract.protocol), joinedload(ProtocolExtract.laureate_award))
        .filter(ProtocolExtract.id == extract_id)
        .first()
    )
    if not e:
        raise HTTPException(status_code=404, detail="Extract not found")

    la = (
        db.query(LaureateAward)
        .options(joinedload(LaureateAward.laureate), joinedload(LaureateAward.award))
        .filter(LaureateAward.id == e.laureate_award_id)
        .first()
    )

    proto_num = str(e.protocol.number if e.protocol else "")
    award_type = la.award.award_type.value if la and la.award and la.award.award_type else None
    is_ppz = award_type == "ppz" or "-З" in proto_num.upper()

    extract_no = proto_num
    if is_ppz and proto_num and "-З" not in proto_num.upper():
        extract_no = f"{proto_num}-З"

    mapping = {
        "EXTRACT_NUMBER": extract_no or "—",
        "PROTOCOL_NUMBER": proto_num or "—",
        "PROTOCOL_DATE": str(e.protocol.date if e.protocol else "—"),
        "FULL_NAME": la.laureate.full_name if la and la.laureate else "—",
        "AWARD_NAME": la.award.name if la and la.award else "—",
        "EXTRACT_DATE": str(e.extract_date or "—"),
        "DETAILS": e.details or "—",
    }
    path = EXTRACT_PPZ_TEMPLATE_PATH if is_ppz else EXTRACT_MEDAL_TEMPLATE_PATH
    label = "Выписка (ППЗ)" if is_ppz else "Выписка (медаль)"
    content = render_template(path, label, mapping)
    filename = f"Выписка_{_safe_filename(str(e.protocol.number if e.protocol else 'protocol'))}_{extract_id}.docx"
    headers = {"Content-Disposition": _content_disposition(filename)}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


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


@router.get("/ppz-submissions", response_model=List[PPZSubmissionRead])
def list_ppz_submissions(db: Session = Depends(get_db)):
    return db.query(PPZSubmission).all()


@router.delete("/ppz-submissions/{ppz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ppz_submission(ppz_id: int, db: Session = Depends(get_db)):
    obj = db.query(PPZSubmission).filter(PPZSubmission.id == ppz_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="PPZ submission not found")
    db.delete(obj)
    db.commit()


@router.get("/ppz-submissions/{ppz_id}/docx")
def ppz_submission_docx(ppz_id: int, db: Session = Depends(get_db)):
    obj = (
        db.query(PPZSubmission)
        .options(joinedload(PPZSubmission.authorized_member))
        .filter(PPZSubmission.id == ppz_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="PPZ submission not found")

    la = (
        db.query(LaureateAward)
        .options(joinedload(LaureateAward.laureate), joinedload(LaureateAward.award))
        .filter(LaureateAward.id == obj.laureate_award_id)
        .first()
    )

    mapping = {
        "SUBMISSION_NUMBER": str(obj.submission_number or "—"),
        "DATE": str(obj.date or "—"),
        "AUTHORIZED": obj.authorized_member.full_name if obj.authorized_member else "—",
        "FULL_NAME": la.laureate.full_name if la and la.laureate else "—",
        "AWARD_NAME": la.award.name if la and la.award else "—",
        "DETAILS": obj.details or "—",
    }
    content = render_template(PPZ_SUBMISSION_TEMPLATE_PATH, "Представление ППЗ", mapping)
    filename = f"ППЗ_{ppz_id}_{_safe_filename(la.laureate.full_name if la and la.laureate else 'laureate')}.docx"
    headers = {"Content-Disposition": _content_disposition(filename)}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
