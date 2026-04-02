"""
Загрузка данных из migration/csv_export/*.csv в PostgreSQL (с полной очисткой пользовательских таблиц).

Ожидаются CSV после dump_access_to_csv.py (разделитель «;», UTF-8 BOM).

Картинки наград: файлы с именами из колонок «Изображение» / «Экскиз медали/ППЗ»
ищутся в папке с .accdb (ACCDB_PATH), в AWARD_IMAGES_DIRS (через «;»),
в корне проекта и в папке award_images/.

Запуск из корня репозитория:
    python migration/import_from_csv.py

Переменные окружения:
    DATABASE_URL — строка подключения PostgreSQL (как у сервера)
    CSV_DIR      — каталог с CSV (по умолчанию migration/csv_export)
"""
from __future__ import annotations

import csv
import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))
os.chdir(SERVER)

from sqlalchemy import text  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402

import models.award  # noqa: F401, E402
import models.laureate  # noqa: F401, E402
import models.committee  # noqa: F401, E402
import models.voting  # noqa: F401, E402
import models.access_mirror  # noqa: F401, E402

from models.award import (  # noqa: E402
    Award,
    AwardCharacteristic,
    AwardType,
    InventoryItem,
    ComponentType,
)
from models.laureate import (  # noqa: E402
    Laureate,
    LaureateAward,
    LaureateLifecycle,
    LaureateCategory,
)
from models.committee import CommitteeMember  # noqa: E402
from models.access_mirror import AccessMirrorRow  # noqa: E402
from models.voting import (  # noqa: E402
    Bulletin,
    BulletinSection,
    BulletinQuestion,
    BulletinDistribution,
    Vote,
    VoteValue,
    Protocol,
    ProtocolStatus,
    ProtocolExtract,
    PPZSubmission,
)


def _parse_bool(v) -> bool:
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in ("true", "1", "yes", "да")


def _parse_int(v, default: int = 0) -> int:
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(float(str(v).replace(",", ".").replace(" ", "")))
    except (TypeError, ValueError):
        return default


def _parse_date(v) -> date | None:
    if v is None or str(v).strip() == "":
        return None
    s = str(v).strip().split()[0][:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_dt(v) -> datetime | None:
    if v is None or str(v).strip() == "":
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _norm_name(s) -> str:
    if not s:
        return ""
    return " ".join(str(s).split())


def _read_dict_rows(csv_path: Path) -> list[dict]:
    if not csv_path.is_file():
        return []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _first(row: dict, *keys: str):
    for k in keys:
        if k in row and row.get(k) not in (None, ""):
            return row.get(k)
    return None


def _find_csv(csv_dir: Path, *stems: str) -> Path | None:
    for stem in stems:
        p = csv_dir / f"{stem}.csv"
        if p.is_file():
            return p
    # fallback: case-insensitive match
    want = {s.lower() for s in stems}
    for p in csv_dir.glob("*.csv"):
        if p.stem.lower() in want:
            return p
    return None


def _import_voting(db, csv_dir: Path) -> None:
    """
    Опциональный импорт голосования, если в CSV есть соответствующие таблицы.
    Поддерживает разные имена файлов/колонок (рус/англ).
    """
    # ── Bulletins ────────────────────────────────────────────────────
    p = _find_csv(csv_dir, "bulletins", "Бюллетени", "Бюллетень", "БюллетениНК", "Bulletins")
    bulletins_by_id: dict[int, Bulletin] = {}
    if p:
        rows = _read_dict_rows(p)
        for row in rows:
            bid = _parse_int(_first(row, "id", "ID", "Код", "КодБюллетеня"), default=0)
            number = str(_first(row, "number", "Номер", "НомерБюллетеня") or "").strip()
            if not number and bid == 0:
                continue
            obj = Bulletin(
                number=number or str(bid),
                voting_start=_parse_date(_first(row, "voting_start", "start_date", "ДатаНачала", "Дата начала")),
                voting_end=_parse_date(_first(row, "voting_end", "end_date", "ДатаОкончания", "Дата окончания")),
                postal_address=str(_first(row, "postal_address", "Адрес", "Почтовый адрес") or "").strip() or None,
            )
            if bid:
                obj.id = bid
            db.add(obj)
            bulletins_by_id[obj.id] = obj
        db.flush()
        print(f"  voting: bulletins imported from {p.name}: {len(rows)}")

    # ── Sections ──────────────────────────────────────────────────────
    p = _find_csv(csv_dir, "bulletin_sections", "РазделыБюллетеня", "BulletinSections")
    sections_by_id: dict[int, BulletinSection] = {}
    if p:
        rows = _read_dict_rows(p)
        for row in rows:
            sid = _parse_int(_first(row, "id", "ID", "Код"), default=0)
            bulletin_id = _parse_int(_first(row, "bulletin_id", "КодБюллетеня", "BulletinID"), default=0)
            if not bulletin_id:
                continue
            name = str(_first(row, "section_name", "Название", "Раздел") or "").strip()
            order = _parse_int(_first(row, "section_order", "Порядок", "Номер"), default=0)
            obj = BulletinSection(bulletin_id=bulletin_id, section_name=name, section_order=order)
            if sid:
                obj.id = sid
            db.add(obj)
            sections_by_id[obj.id] = obj
        db.flush()
        print(f"  voting: sections imported from {p.name}: {len(rows)}")

    # ── Questions ──────────────────────────────────────────────────────
    p = _find_csv(csv_dir, "bulletin_questions", "ВопросыБюллетеня", "BulletinQuestions")
    if p:
        rows = _read_dict_rows(p)
        for row in rows:
            qid = _parse_int(_first(row, "id", "ID", "Код"), default=0)
            section_id = _parse_int(_first(row, "section_id", "КодРаздела", "SectionID"), default=0)
            if not section_id:
                continue
            text_q = str(_first(row, "question_text", "Текст", "Вопрос") or "").strip()
            order = _parse_int(_first(row, "question_order", "Порядок", "Номер"), default=0)
            laureate_award_id = _parse_int(_first(row, "laureate_award_id", "КодСвязки", "LaureateAwardID"), default=0) or None
            initiator = str(_first(row, "initiator", "Инициатор") or "").strip() or None
            obj = BulletinQuestion(
                section_id=section_id,
                question_text=text_q,
                question_order=order,
                laureate_award_id=laureate_award_id,
                initiator=initiator,
            )
            if qid:
                obj.id = qid
            db.add(obj)
        db.flush()
        print(f"  voting: questions imported from {p.name}: {len(rows)}")

    # ── Distributions ──────────────────────────────────────────────────
    p = _find_csv(csv_dir, "bulletin_distributions", "РассылкаБюллетеней", "BulletinDistributions")
    if p:
        rows = _read_dict_rows(p)
        for row in rows:
            did = _parse_int(_first(row, "id", "ID", "Код"), default=0)
            bulletin_id = _parse_int(_first(row, "bulletin_id", "КодБюллетеня", "BulletinID"), default=0)
            member_id = _parse_int(_first(row, "member_id", "КодЧленаНК", "MemberID"), default=0)
            if not bulletin_id or not member_id:
                continue
            obj = BulletinDistribution(
                bulletin_id=bulletin_id,
                member_id=member_id,
                sent=_parse_bool(_first(row, "sent", "Отправлено")),
                sent_date=_parse_date(_first(row, "sent_date", "ДатаОтправки")),
                received=_parse_bool(_first(row, "received", "Получено")),
                received_date=_parse_date(_first(row, "received_date", "ДатаПолучения")),
            )
            if did:
                obj.id = did
            db.add(obj)
        db.flush()
        print(f"  voting: distributions imported from {p.name}: {len(rows)}")

    # ── Votes ──────────────────────────────────────────────────────────
    p = _find_csv(csv_dir, "votes", "Голоса", "Votes")
    if p:
        rows = _read_dict_rows(p)
        for row in rows:
            vid = _parse_int(_first(row, "id", "ID", "Код"), default=0)
            question_id = _parse_int(_first(row, "question_id", "КодВопроса", "QuestionID"), default=0)
            member_id = _parse_int(_first(row, "member_id", "КодЧленаНК", "MemberID"), default=0)
            if not question_id or not member_id:
                continue
            v = _first(row, "value", "Значение", "vote_for", "За")
            if isinstance(v, str) and v.strip().lower() in ("against", "против", "false", "0", "нет"):
                value = VoteValue.AGAINST
            elif v is not None and str(v).strip().lower() in ("for", "за", "true", "1", "да"):
                value = VoteValue.FOR
            else:
                value = VoteValue.FOR
            voted_at = _parse_dt(_first(row, "voted_at", "ДатаГолоса"))
            obj = Vote(question_id=question_id, member_id=member_id, value=value)
            if voted_at:
                obj.voted_at = voted_at
            if vid:
                obj.id = vid
            db.add(obj)
        db.flush()
        print(f"  voting: votes imported from {p.name}: {len(rows)}")

    # ── Protocols ──────────────────────────────────────────────────────
    p = _find_csv(csv_dir, "protocols", "Протоколы", "Protocols")
    if p:
        rows = _read_dict_rows(p)
        for row in rows:
            pid = _parse_int(_first(row, "id", "ID", "Код"), default=0)
            bulletin_id = _parse_int(_first(row, "bulletin_id", "КодБюллетеня", "BulletinID"), default=0)
            number = str(_first(row, "number", "Номер") or "").strip()
            if not bulletin_id or not number:
                continue
            st = str(_first(row, "status", "Статус") or "").strip().lower()
            status = ProtocolStatus.SIGNED if st in ("signed", "подписан") else ProtocolStatus.DRAFT
            obj = Protocol(
                bulletin_id=bulletin_id,
                number=number,
                date=_parse_date(_first(row, "date", "Дата")),
                status=status,
                details=str(_first(row, "details", "Детали", "Описание") or "").strip() or None,
            )
            if pid:
                obj.id = pid
            db.add(obj)
        db.flush()
        print(f"  voting: protocols imported from {p.name}: {len(rows)}")

    # ── Extracts ───────────────────────────────────────────────────────
    p = _find_csv(csv_dir, "protocol_extracts", "Выписки", "ProtocolExtracts")
    if p:
        rows = _read_dict_rows(p)
        for row in rows:
            eid = _parse_int(_first(row, "id", "ID", "Код"), default=0)
            protocol_id = _parse_int(_first(row, "protocol_id", "КодПротокола", "ProtocolID"), default=0)
            laureate_award_id = _parse_int(_first(row, "laureate_award_id", "КодСвязки", "LaureateAwardID"), default=0)
            if not protocol_id or not laureate_award_id:
                continue
            obj = ProtocolExtract(
                protocol_id=protocol_id,
                laureate_award_id=laureate_award_id,
                extract_date=_parse_date(_first(row, "extract_date", "Дата")),
                details=str(_first(row, "details", "Детали", "Описание") or "").strip() or None,
            )
            if eid:
                obj.id = eid
            db.add(obj)
        db.flush()
        print(f"  voting: extracts imported from {p.name}: {len(rows)}")

    # ── PPZ submissions ────────────────────────────────────────────────
    p = _find_csv(csv_dir, "ppz_submissions", "ПредставленияППЗ", "PPZSubmissions")
    if p:
        rows = _read_dict_rows(p)
        for row in rows:
            pid = _parse_int(_first(row, "id", "ID", "Код"), default=0)
            laureate_award_id = _parse_int(_first(row, "laureate_award_id", "КодСвязки", "LaureateAwardID"), default=0)
            auth_id = _parse_int(_first(row, "authorized_member_id", "КодУполномоченного", "AuthorizedMemberID"), default=0)
            if not laureate_award_id or not auth_id:
                continue
            obj = PPZSubmission(
                laureate_award_id=laureate_award_id,
                authorized_member_id=auth_id,
                submission_number=str(_first(row, "submission_number", "Номер") or "").strip() or None,
                date=_parse_date(_first(row, "date", "Дата")),
                details=str(_first(row, "details", "Детали", "Описание") or "").strip() or None,
            )
            if pid:
                obj.id = pid
            db.add(obj)
        db.flush()
        print(f"  voting: ppz submissions imported from {p.name}: {len(rows)}")


def _characteristic_cell_value(val) -> str | None:
    """Значение ячейки Access → строка для хранения; пустое — не импортируем."""
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    low = s.lower()
    if low == "true":
        return "Да"
    if low == "false":
        return "Нет"
    return s


def _infer_award_type(row: dict) -> AwardType:
    m = _parse_bool(row.get("Медаль"))
    p = _parse_bool(row.get("ППЗ"))
    if p and not m:
        return AwardType.PPZ
    if m:
        return AwardType.MEDAL
    return AwardType.DECORATION


def _infer_laureate_category(row: dict) -> LaureateCategory | None:
    order = [
        ("Сотрудник организации", LaureateCategory.EMPLOYEE),
        ("Ветеран", LaureateCategory.VETERAN),
        ("Универ", LaureateCategory.UNIVERSITY),
        ("НИИ", LaureateCategory.NII),
        ("Неком орг", LaureateCategory.NONPROFIT),
        ("Ком орг", LaureateCategory.COMMERCIAL),
    ]
    for key, cat in order:
        if _parse_bool(row.get(key)):
            return cat
    return None


def _image_filenames_from_row(row: dict) -> list[str]:
    """Имена файлов из полей Access, где обычно лежат эскизы."""
    keys = ("Изображение", "Экскиз медали/ППЗ", "Экскиз значка")
    seen: set[str] = set()
    out: list[str] = []
    for k in keys:
        v = row.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if len(s) < 4:
            continue
        low = s.lower()
        if low in ("false", "true", "-", "none"):
            continue
        if low.startswith("введите"):
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _image_search_dirs() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    raw = os.environ.get("AWARD_IMAGES_DIRS", "")
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            p = Path(part).expanduser().resolve()
        except OSError:
            continue
        if p.is_dir() and p not in seen:
            seen.add(p)
            out.append(p)
    accdb = os.environ.get("ACCDB_PATH", "").strip()
    if accdb:
        try:
            p = Path(accdb).expanduser().resolve().parent
            if p.is_dir() and p not in seen:
                seen.add(p)
                out.append(p)
        except OSError:
            pass
    for rel in (
        ROOT,
        ROOT / "award_images",
        ROOT / "images",
        ROOT / "client" / "resources" / "award_images",
    ):
        try:
            p = rel.resolve()
            if p.is_dir() and p not in seen:
                seen.add(p)
                out.append(p)
        except OSError:
            pass
    return out


def _resolve_award_image_bytes(row: dict) -> bytes | None:
    """Читает файл картинки с диска по имени из CSV (как в Access)."""
    for fn in _image_filenames_from_row(row):
        for d in _image_search_dirs():
            p = d / fn
            if p.is_file():
                try:
                    return p.read_bytes()
                except OSError:
                    continue
    return None


def _map_component_type(kind: str, row_medal, row_ppz) -> ComponentType:
    t = (kind or "").lower()
    if _parse_bool(row_ppz) or "ппз" in t:
        return ComponentType.PPZ
    if "значок" in t or "знак" in t:
        return ComponentType.BADGE
    if "запонк" in t:
        return ComponentType.CUFFLINKS
    if "кулон" in t:
        return ComponentType.PENDANT
    if "удостовер" in t:
        return ComponentType.CERTIFICATE
    if "футляр" in t:
        return ComponentType.CASE
    if "короб" in t:
        return ComponentType.BOX
    return ComponentType.MEDAL


def _truncate_all(conn) -> None:
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))


def _json_cell(val):
    """Значение ячейки → JSON-совместимый тип для JSONB."""
    if val is None:
        return None
    if isinstance(val, (bytes, bytearray, memoryview)):
        return f"<binary {len(val)} байт>"
    return val


def _mirror_all_csv(db, csv_dir: Path) -> int:
    """Полное зеркало каждого CSV: те же столбцы и строки, что в выгрузке Access."""
    total = 0
    for path in sorted(csv_dir.glob("*.csv")):
        stem = path.stem
        rows = _read_dict_rows(path)
        for idx, row in enumerate(rows):
            data = {str(k): _json_cell(v) for k, v in row.items()}
            db.add(AccessMirrorRow(table_name=stem, row_index=idx, data=data))
            total += 1
        if rows:
            print(f"  mirror CSV -> access_mirror_rows: {stem} ({len(rows)} строк)")
    return total


def main() -> None:
    csv_dir = Path(os.environ.get("CSV_DIR", str(ROOT / "migration" / "csv_export")))

    mega = csv_dir / "НаградыМега.csv"
    lau = csv_dir / "Лауреаты.csv"
    lc = csv_dir / "ЛАУР_ЖЦ.csv"
    nk = csv_dir / "Список НК.csv"
    uch = csv_dir / "УЧ_комплекты_наград.csv"

    with engine.begin() as conn:
        _truncate_all(conn)

    db = SessionLocal()
    try:
        award_by_name: dict[str, int] = {}
        for row in _read_dict_rows(mega):
            name = _norm_name(row.get("Название награды"))
            if not name:
                continue
            img_bytes = _resolve_award_image_bytes(row)
            a = Award(
                name=name,
                award_type=_infer_award_type(row),
                image_front=img_bytes,
            )
            db.add(a)
            db.flush()
            award_by_name[name] = a.id
            for col, raw in row.items():
                if col == "Название награды":
                    continue
                v = _characteristic_cell_value(raw)
                if v is None:
                    continue
                db.add(
                    AwardCharacteristic(
                        award_id=a.id,
                        field_name=str(col),
                        field_value=v,
                    )
                )

        for row in _read_dict_rows(nk):
            fn = _norm_name(row.get("ФИО"))
            if not fn:
                continue
            mob = (row.get("Тел (моб)") or "").strip()
            wrk = (row.get("Тел (раб)") or "").strip()
            phone = mob or wrk or None
            pos = (row.get("Позиция") or "")[:500]
            db.add(
                CommitteeMember(
                    full_name=fn[:500],
                    position=pos or None,
                    organization=None,
                    phone=phone[:100] if phone else None,
                    email=(row.get("Почта") or "").strip()[:255] or None,
                    is_active=True,
                )
            )

        for row in _read_dict_rows(lau):
            fn = _norm_name(row.get("ФИО"))
            if not fn or len(fn) < 3:
                continue
            db.add(
                Laureate(
                    full_name=fn[:500],
                    category=_infer_laureate_category(row),
                    position=(row.get("Должность") or "").strip()[:500] or None,
                    organization=(row.get("Организация") or "").strip()[:500] or None,
                )
            )
        db.flush()

        laureate_by_name: dict[str, int] = {}
        for x in db.query(Laureate).all():
            laureate_by_name[_norm_name(x.full_name)] = x.id

        lc_rows = _read_dict_rows(lc)
        csv_by_pair: dict[tuple[int, int], dict] = {}
        skipped_lc = 0
        for row in lc_rows:
            an = _norm_name(row.get("Название награды"))
            fn = _norm_name(row.get("ФИО"))
            aid = award_by_name.get(an)
            lid = laureate_by_name.get(fn)
            if not aid or not lid:
                skipped_lc += 1
                continue
            key = (lid, aid)
            if key not in csv_by_pair:
                csv_by_pair[key] = row

        for (lid, aid), row in csv_by_pair.items():
            bulletin = (row.get("Бюллетень") or "").strip() or None
            db.add(
                LaureateAward(
                    laureate_id=lid,
                    award_id=aid,
                    assigned_date=_parse_date(row.get("ВЫДВИЖ_дата")),
                    bulletin_number=bulletin[:50] if bulletin else None,
                    initiator=(row.get("ВЫДВИЖ_лицо") or "").strip()[:500] or None,
                    status="imported",
                )
            )
        db.flush()

        for la in db.query(LaureateAward).all():
            lrow = csv_by_pair.get((la.laureate_id, la.award_id))
            if not lrow:
                continue
            place_parts = [
                x
                for x in (
                    (lrow.get("ВРУЧЕН_кто") or "").strip(),
                    (lrow.get("ВРУЧЕН_где") or "").strip(),
                )
                if x
            ]
            ceremony_place = ", ".join(place_parts)[:500] if place_parts else None
            db.add(
                LaureateLifecycle(
                    laureate_award_id=la.id,
                    nomination_date=_parse_date(lrow.get("ВЫДВИЖ_дата")),
                    nomination_initiator=(lrow.get("ВЫДВИЖ_лицо") or "").strip()[:500] or None,
                    nomination_done=_parse_bool(lrow.get("ВЫДВИЖ_чек")),
                    voting_date=_parse_date(lrow.get("СОГЛАС_секретариарт_дата")),
                    voting_bulletin_number=(lrow.get("Бюллетень") or "").strip()[:50] or None,
                    voting_done=_parse_bool(lrow.get("СОГЛАС_чек")),
                    decision_date=_parse_date(lrow.get("ПРИСУЖ_дата")),
                    decision_protocol_number=(
                        (lrow.get("ПРИСУЖ_№ протокола") or "").strip()[:50] or None
                    ),
                    decision_done=_parse_bool(lrow.get("ПРИСУЖ_чек")),
                    registration_date=_parse_date(lrow.get("ОФОРМ_дата")),
                    registration_certificate_number=(
                        (lrow.get("ОФОРМ_выписка_№") or "").strip()[:100] or None
                    ),
                    registration_done=_parse_bool(lrow.get("ОФОРМ_чек")),
                    ceremony_date=_parse_date(lrow.get("ВРУЧЕН_дата")),
                    ceremony_place=ceremony_place,
                    ceremony_done=_parse_bool(lrow.get("ВРУЧЕН_чек")),
                    publication_date=_parse_date(lrow.get("ОПУБЛ_НК_дата")),
                    publication_done=_parse_bool(lrow.get("ОПУБЛ_чек")),
                )
            )

        inv_seen: set[tuple[int, str]] = set()
        for row in _read_dict_rows(uch):
            an = _norm_name(row.get("Название награды"))
            aid = award_by_name.get(an)
            if not aid:
                continue
            ct = _map_component_type(
                row.get("Тип комплекта") or "",
                row.get("Медаль"),
                row.get("ППЗ"),
            )
            qty = _parse_int(row.get("Количество в наличии"))
            key = (aid, ct.value)
            if key in inv_seen:
                ex = (
                    db.query(InventoryItem)
                    .filter(
                        InventoryItem.award_id == aid,
                        InventoryItem.component_type == ct,
                    )
                    .first()
                )
                if ex:
                    ex.total_count = (ex.total_count or 0) + qty
                    ex.available_count = (ex.available_count or 0) + qty
                continue
            inv_seen.add(key)
            db.add(
                InventoryItem(
                    award_id=aid,
                    component_type=ct,
                    total_count=qty,
                    reserve_count=0,
                    issued_count=0,
                    available_count=qty,
                )
            )

        n_mirror = _mirror_all_csv(db, csv_dir)

        # Опционально: голосование (если таблицы присутствуют в CSV)
        _import_voting(db, csv_dir)

        db.commit()
        print(
            f"Импорт завершён из {csv_dir}:\n"
            f"  награды: {len(award_by_name)}, "
            f"лауреаты: {len(laureate_by_name)}, "
            f"связей лауреат–награда: {len(csv_by_pair)}, "
            f"пропусков ЖЦ (нет ФИО/награды в справочнике): {skipped_lc}\n"
            f"  зеркало всех таблиц Access (CSV): {n_mirror} строк в access_mirror_rows"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
