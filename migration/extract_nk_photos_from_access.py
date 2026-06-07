"""
Извлечение фото членов НК из Access (таблица «Список НК», поле «Фото», type=101)
и загрузка в PostgreSQL / сохранение на диск.

Фото в CSV указаны только именами (агеев.jpg); сами файлы лежат в backend .accdb:
  data/legacy/access/БД - награды - V2  - 24-08-2023_be.accdb

Запуск из корня:
  python migration/extract_nk_photos_from_access.py --dry-run
  python migration/extract_nk_photos_from_access.py --save-disk
  python migration/extract_nk_photos_from_access.py          # сразу в PostgreSQL
  python migration/import_person_photos.py --from-access    # extract + import
"""
from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))
os.chdir(SERVER)

try:
    import win32com.client as w32
except ImportError:
    print("Установите: pip install pywin32")
    sys.exit(1)

from sqlalchemy.orm import Session  # noqa: E402
from database import SessionLocal  # noqa: E402
import models.committee  # noqa: F401, E402
from models.committee import CommitteeMember  # noqa: E402

ACCESS_TABLE = "Список НК"
NAME_FIELD = "ФИО"
PHOTO_FIELD = "Фото"
DAO_TYPE_ATTACHMENT = 101
OUT_DIR = ROOT / "data" / "photos" / "nk"


def _parse_attachment_data(raw: bytes) -> bytes:
    if len(raw) < 4:
        return raw
    header_size = struct.unpack_from("<I", raw, 0)[0]
    if header_size >= len(raw):
        return raw[4:]
    return raw[header_size:]


def _find_backend_accdb() -> Path | None:
    env = os.environ.get("ACCDB_BACKEND", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_file():
            return p
    legacy = ROOT / "data" / "legacy" / "access"
    if not legacy.is_dir():
        return None
    # backend обычно *_be.accdb
    for pattern in ("*_be.accdb", "*be.accdb"):
        hits = sorted(legacy.glob(pattern))
        if hits:
            return hits[0]
    for p in sorted(legacy.glob("*.accdb")):
        if "архив" not in p.name.lower():
            try:
                engine = w32.Dispatch("DAO.DBEngine.120")
                db = engine.OpenDatabase(str(p))
                for t in db.TableDefs:
                    if t.Name == ACCESS_TABLE and t.Attributes == 0:
                        db.Close()
                        return p
                db.Close()
            except Exception:
                pass
    return None


def _open_db(accdb: Path):
    engine = w32.Dispatch("DAO.DBEngine.120")
    return engine.OpenDatabase(str(accdb))


def extract_nk_photos(accdb: Path) -> list[tuple[str, str, bytes]]:
    """(full_name, filename, image_bytes)"""
    db = _open_db(accdb)
    out: list[tuple[str, str, bytes]] = []
    try:
        rs = db.OpenRecordset(ACCESS_TABLE)
        if rs.BOF and rs.EOF:
            return out
        rs.MoveFirst()
        while not rs.EOF:
            name = rs.Fields(NAME_FIELD).Value
            if not name:
                rs.MoveNext()
                continue
            try:
                att_rs = rs.Fields(PHOTO_FIELD).Value
                if att_rs is None or (att_rs.BOF and att_rs.EOF):
                    if att_rs is not None:
                        att_rs.Close()
                    rs.MoveNext()
                    continue
                att_rs.MoveFirst()
                while not att_rs.EOF:
                    raw = att_rs.Fields("FileData").Value
                    fname = att_rs.Fields("FileName").Value or "photo.jpg"
                    if raw:
                        img = _parse_attachment_data(bytes(raw))
                        if img:
                            out.append((str(name).strip(), str(fname).strip(), img))
                            break
                    att_rs.MoveNext()
                att_rs.Close()
            except Exception:
                pass
            rs.MoveNext()
    finally:
        db.Close()
    return out


def _norm_name(s: str) -> str:
    return " ".join((s or "").split()).lower()


def save_to_disk(items: list[tuple[str, str, bytes]]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    for _name, fname, data in items:
        path = OUT_DIR / fname
        if path.exists() and path.read_bytes() == data:
            continue
        path.write_bytes(data)
        saved += 1
        print(f"  [DISK] {fname} ({len(data):,} bytes)")
    return saved


def save_to_postgres(items: list[tuple[str, str, bytes]]) -> tuple[int, int]:
    db: Session = SessionLocal()
    by_name = {_norm_name(m.full_name): m for m in db.query(CommitteeMember).all()}
    updated = missed = 0
    try:
        for full_name, fname, data in items:
            member = by_name.get(_norm_name(full_name))
            if member is None:
                print(f"  [SKIP] нет в БД: {full_name}")
                missed += 1
                continue
            member.photo = data
            member.photo_filename = fname
            updated += 1
            print(f"  [PG] {full_name} <- {fname} ({len(data):,} bytes)")
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return updated, missed


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--save-disk", action="store_true", help="Сохранить в data/photos/nk/")
    p.add_argument("--accdb", help="Путь к backend .accdb (по умолчанию *_be.accdb)")
    args = p.parse_args()

    accdb = Path(args.accdb).expanduser().resolve() if args.accdb else _find_backend_accdb()
    if accdb is None or not accdb.is_file():
        print("Backend Access не найден. Укажите ACCDB_BACKEND или положите *_be.accdb в data/legacy/access/")
        sys.exit(1)

    print(f"Access backend: {accdb}")
    print("Извлечение фото НК…")
    items = extract_nk_photos(accdb)
    print(f"Найдено фото: {len(items)}")
    if not items:
        print("Нечего импортировать.")
        return

    if args.dry_run:
        for name, fname, data in items[:5]:
            print(f"  {name} <- {fname} ({len(data):,} bytes)")
        if len(items) > 5:
            print(f"  … и ещё {len(items) - 5}")
        return

    if args.save_disk or os.environ.get("SAVE_NK_DISK", "").strip() in ("1", "true"):
        n = save_to_disk(items)
        print(f"На диск записано: {n} файлов в {OUT_DIR}")
        if not args.save_disk:
            return

    if not args.save_disk:
        updated, missed = save_to_postgres(items)
        print(f"PostgreSQL: обновлено {updated}, пропусков {missed}")


if __name__ == "__main__":
    main()
