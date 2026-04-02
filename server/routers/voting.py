from datetime import date as dt_date
import re
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from typing import List
from docx import Document

from database import get_db
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


def _safe_filename(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]+", "_", s or "").strip()
    return s or "document"


def _docx_response(doc: Document, filename: str) -> Response:
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
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
    """DOCX-версия бюллетеня (для Word)."""
    b = (
        db.query(Bulletin)
        .options(joinedload(Bulletin.sections).joinedload(BulletinSection.questions))
        .filter(Bulletin.id == bulletin_id)
        .first()
    )
    if not b:
        raise HTTPException(status_code=404, detail="Bulletin not found")

    doc = Document()
    doc.add_heading(f"Бюллетень голосования № {b.number}", level=1)
    doc.add_paragraph(f"Период голосования: {b.voting_start or '—'} — {b.voting_end or '—'}")
    doc.add_paragraph(f"Адрес: {b.postal_address or '—'}")

    sections = sorted(b.sections, key=lambda x: (x.section_order or 0, x.id))
    if not sections:
        doc.add_paragraph("Вопросы не добавлены.")
    for s in sections:
        doc.add_heading(str(s.section_name or ""), level=2)
        questions = sorted(s.questions, key=lambda q: (q.question_order or 0, q.id))
        for idx, q in enumerate(questions, 1):
            doc.add_paragraph(f"{idx}. {q.question_text}", style="List Number")

    filename = f"Бюллетень_{_safe_filename(str(b.number))}.docx"
    return _docx_response(doc, filename)


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


@router.get("/protocols/{protocol_id}/docx")
def protocol_docx(protocol_id: int, db: Session = Depends(get_db)):
    """DOCX-версия протокола с результатами голосования."""
    p = (
        db.query(Protocol)
        .options(joinedload(Protocol.bulletin))
        .filter(Protocol.id == protocol_id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="Protocol not found")

    results = vote_results(p.bulletin_id, db)

    doc = Document()
    doc.add_heading(f"Протокол № {p.number}", level=1)
    doc.add_paragraph(f"Дата: {p.date or '—'}")
    doc.add_paragraph(f"Бюллетень: {p.bulletin.number if p.bulletin else p.bulletin_id}")
    doc.add_paragraph(f"Статус: {p.status.value if p.status else '—'}")
    if p.details:
        doc.add_paragraph(p.details)

    doc.add_heading("Результаты голосования", level=2)
    if not results:
        doc.add_paragraph("Нет данных.")
    else:
        table = doc.add_table(rows=1, cols=4)
        hdr = table.rows[0].cells
        hdr[0].text = "Вопрос"
        hdr[1].text = "За"
        hdr[2].text = "Против"
        hdr[3].text = "% За"
        for r in results:
            row = table.add_row().cells
            row[0].text = str(r.question_text)
            row[1].text = str(r.votes_for)
            row[2].text = str(r.votes_against)
            row[3].text = f"{r.percent_for:.1f}%"

    filename = f"Протокол_{_safe_filename(str(p.number))}.docx"
    return _docx_response(doc, filename)


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

    doc = Document()
    doc.add_heading("Выписка из протокола", level=1)
    doc.add_paragraph(f"Протокол: № {e.protocol.number if e.protocol else '—'} от {e.protocol.date if e.protocol else '—'}")
    if la and la.laureate:
        doc.add_paragraph(f"Лауреат: {la.laureate.full_name}")
    if la and la.award:
        doc.add_paragraph(f"Награда: {la.award.name}")
    doc.add_paragraph(f"Дата выписки: {e.extract_date or '—'}")
    if e.details:
        doc.add_paragraph(e.details)

    filename = f"Выписка_{_safe_filename(str(e.protocol.number if e.protocol else 'protocol'))}_{extract_id}.docx"
    return _docx_response(doc, filename)


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

    doc = Document()
    doc.add_heading("Представление на награждение (ППЗ)", level=1)
    doc.add_paragraph(f"Номер: {obj.submission_number or '—'}")
    doc.add_paragraph(f"Дата: {obj.date or '—'}")
    if obj.authorized_member:
        doc.add_paragraph(f"Уполномоченный: {obj.authorized_member.full_name}")
    if la and la.laureate:
        doc.add_paragraph(f"Лауреат: {la.laureate.full_name}")
    if la and la.award:
        doc.add_paragraph(f"Награда: {la.award.name}")
    if obj.details:
        doc.add_paragraph(obj.details)

    filename = f"ППЗ_{ppz_id}_{_safe_filename(la.laureate.full_name if la and la.laureate else 'laureate')}.docx"
    return _docx_response(doc, filename)
