"""
Миграция изображений наград из Microsoft Access → PostgreSQL.

Поддерживает три режима источника изображений:

1. --source access  (по умолчанию, только Windows + pywin32)
   Читает Attachment-поля таблицы НаградыМега напрямую из .accdb через DAO COM.

2. --source dir --images-dir ПУТЬ
   Сканирует папку с файлами изображений (.jpg/.png/.bmp и т.д.) и сопоставляет
   их с наградами по имени файла / названию награды.

3. --source csv
   Читает migration/csv_export/НаградыМега.csv, берёт колонки с именами
   изображений (Изображение, Эскиз медали/ППЗ и т.д.), ищет файлы в папке
   ACCDB_PATH (рядом с базой) или --images-dir.

Переменные окружения:
  ACCDB_PATH   — путь к .accdb (для режимов access и csv)
  DATABASE_URL — строка подключения PostgreSQL (как у сервера)
  DRY_RUN=1    — только показать, что будет сделано

Запуск:
  python migration/migrate_images.py --source access --dry-run
  python migration/migrate_images.py --source dir --images-dir C:/images
  python migration/migrate_images.py --source csv --images-dir C:/images
  python migration/migrate_images.py --source access --report
"""
from __future__ import annotations

import argparse
import csv
import os
import struct
import sys
import unicodedata
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))

# Разрешаем ACCDB_PATH до смены рабочей директории
_ACCDB_ENV_RAW = os.environ.get("ACCDB_PATH", "").strip()
if _ACCDB_ENV_RAW:
    os.environ["ACCDB_PATH"] = str(Path(_ACCDB_ENV_RAW).expanduser().resolve())

os.chdir(SERVER)

from sqlalchemy.orm import Session  # noqa: E402
from database import SessionLocal  # noqa: E402
import models.award  # noqa: F401, E402
from models.award import Award  # noqa: E402


# ── Константы ─────────────────────────────────────────────────────────────────

ACCESS_TABLE = "НаградыМега"
NAME_FIELD = "Название награды"

# Маппинг: поле Access → колонка PostgreSQL (первый приоритет выигрывает)
FIELD_MAPPING: list[tuple[str, str]] = [
    ("Изображение",          "image_front"),
    ("Эскиз медали/ППЗ",     "image_front"),
    ("Файл_протокол",        "image_front"),
    ("Изображение_оборот",   "image_back"),
    ("Изображение оборот",   "image_back"),
]

# Имена CSV-колонок с путями к файлам изображений
CSV_IMAGE_COLUMNS = [
    "Изображение", "Эскиз медали/ППЗ", "Файл_протокол",
    "Изображение_оборот", "Изображение оборот",
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}

DAO_TYPE_ATTACHMENT = 101


# ── Утилиты ───────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return " ".join(s.lower().split())


def _detect_fmt(data: bytes) -> str:
    if not data or len(data) < 4:
        return "unknown"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if data[:2] == b"\xff\xd8":
        return "JPEG"
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if data[:4] == b"RIFF" and len(data) >= 12 and data[8:12] == b"WEBP":
        return "WEBP"
    if data[:2] == b"BM":
        return "BMP"
    return "unknown"


def _parse_access_attachment(raw: bytes) -> bytes:
    """Access Attachment header: first 4 bytes = uint32 LE header size."""
    if len(raw) < 4:
        return raw
    hdr = struct.unpack_from("<I", raw, 0)[0]
    return raw[hdr:] if hdr < len(raw) else raw


def _accdb_path(cli: str | None) -> Path:
    if cli:
        p = Path(cli).expanduser().resolve()
        if p.is_file():
            return p
        print(f"[ОШИБКА] Файл не найден: {p}")
        sys.exit(1)
    env = os.environ.get("ACCDB_PATH", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_file():
            return p
    for c in sorted(ROOT.glob("*.accdb")):
        if "архив" not in c.name.lower():
            return c
    candidates = list(ROOT.glob("*.accdb"))
    if candidates:
        return candidates[0]
    print("Ошибка: .accdb файл не найден. Укажите --accdb или ACCDB_PATH.")
    sys.exit(1)


# ── Поиск награды в PostgreSQL ────────────────────────────────────────────────

def _find_award(pg: Session, name: str) -> Award | None:
    """Точное → нормализованное → вхождение."""
    a = pg.query(Award).filter(Award.name == name).first()
    if a:
        return a
    norm = _normalize(name)
    for a in pg.query(Award).all():
        if _normalize(a.name) == norm:
            return a
    for a in pg.query(Award).all():
        an = _normalize(a.name)
        if an in norm or norm in an:
            return a
    return None


# ── Запись в PostgreSQL ───────────────────────────────────────────────────────

def _save_images(
    extracted: list[tuple[str, dict[str, bytes]]],
    dry_run: bool,
) -> None:
    if not extracted:
        print("Изображений для загрузки не найдено.")
        return

    by_col: dict[str, int] = {}
    for _, imgs in extracted:
        for col in imgs:
            by_col[col] = by_col.get(col, 0) + 1
    print(f"\nНайдено записей: {len(extracted)}")
    for col, cnt in by_col.items():
        print(f"  {col}: {cnt}")

    if dry_run:
        print("\nDRY RUN — запись пропущена.")
        return

    print("\n=== Запись в PostgreSQL ===")
    pg: Session = SessionLocal()
    updated = skipped = 0
    not_found: list[str] = []
    try:
        for name, imgs in extracted:
            award = _find_award(pg, name)
            if award is None:
                not_found.append(name)
                print(f"  [MISS] «{name}»")
                continue
            changed = False
            for col, data in imgs.items():
                existing = getattr(award, col)
                if existing and len(bytes(existing)) == len(data):
                    skipped += 1
                    print(f"  [SKIP] '{name}' -> {col} already loaded")
                    continue
                setattr(award, col, data)
                print(f"  [SAVE] '{name}' (id={award.id}) -> {col} {_detect_fmt(data)} {len(data):,} bytes")
                changed = True
            if changed:
                updated += 1
        pg.commit()
    except Exception as exc:
        pg.rollback()
        print(f"Ошибка при записи: {exc}")
        raise
    finally:
        pg.close()

    print(f"\nОбновлено: {updated}  |  Пропущено: {skipped}  |  Не найдено: {len(not_found)}")
    if not_found:
        print("Не найдены:", ", ".join(f"«{n}»" for n in not_found))


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 1 — Access COM (Windows + pywin32)
# ═══════════════════════════════════════════════════════════════════════════════

def _open_access_db(accdb: Path):
    try:
        import win32com.client as w32
    except ImportError:
        print("pywin32 не установлен. Выполните: pip install pywin32")
        sys.exit(1)
    engine = w32.Dispatch("DAO.DBEngine.120")
    return engine.OpenDatabase(str(accdb))


def _att_fields_in_table(tdef) -> set[str]:
    return {f.Name for f in tdef.Fields if f.Type == DAO_TYPE_ATTACHMENT}


def run_access_report(accdb: Path) -> None:
    print(f"=== Attachment-поля в {accdb.name} ===\n")
    db = _open_access_db(accdb)
    try:
        tdef = next((t for t in db.TableDefs if t.Name == ACCESS_TABLE), None)
        if tdef is None:
            print(f"Таблица «{ACCESS_TABLE}» не найдена.")
            return
        att = _att_fields_in_table(tdef)
        print(f"Attachment-поля: {att or '(нет)'}\n")
        rs = db.OpenRecordset(ACCESS_TABLE)
        total = 0
        counts: dict[str, int] = {f: 0 for f in att}
        if not (rs.BOF and rs.EOF):
            rs.MoveFirst()
            while not rs.EOF:
                total += 1
                for field in att:
                    try:
                        a = rs.Fields(field).Value
                        if not (a.BOF and a.EOF):
                            counts[field] += 1
                        a.Close()
                    except Exception:
                        pass
                rs.MoveNext()
        rs.Close()
        print(f"Строк: {total}")
        for f, c in counts.items():
            print(f"  {f}: {c} вложений")
    finally:
        db.Close()


def extract_from_access(accdb: Path) -> list[tuple[str, dict[str, bytes]]]:
    db = _open_access_db(accdb)
    result: list[tuple[str, dict[str, bytes]]] = []
    try:
        tdef = next((t for t in db.TableDefs if t.Name == ACCESS_TABLE), None)
        if tdef is None:
            print(f"Таблица «{ACCESS_TABLE}» не найдена.")
            return result

        available = _att_fields_in_table(tdef)
        mapping = [(af, pc) for af, pc in FIELD_MAPPING if af in available]
        if not mapping:
            print("Attachment-поля не найдены.")
            return result

        print(f"Маппинг: {[(af, pc) for af, pc in mapping]}")
        rs = db.OpenRecordset(ACCESS_TABLE)
        if rs.BOF and rs.EOF:
            rs.Close()
            return result

        rs.MoveFirst()
        while not rs.EOF:
            raw_name = rs.Fields(NAME_FIELD).Value
            name = (raw_name or "").strip()
            if not name:
                rs.MoveNext()
                continue

            imgs: dict[str, bytes] = {}
            for acc_f, pg_col in mapping:
                if pg_col in imgs:
                    continue
                try:
                    att_rs = rs.Fields(acc_f).Value
                    # BOF+EOF — единственный надёжный способ проверить пустой dynaset
                    if att_rs.BOF and att_rs.EOF:
                        att_rs.Close()
                        continue
                    att_rs.MoveFirst()
                    while not att_rs.EOF:
                        raw = att_rs.Fields("FileData").Value
                        if raw:
                            data = _parse_access_attachment(bytes(raw))
                            if data:
                                fname = att_rs.Fields("FileName").Value or ""
                                imgs[pg_col] = data
                                print(f"  [{acc_f}->{pg_col}] {fname!r} {_detect_fmt(data)} {len(data):,} b")
                                break
                        att_rs.MoveNext()
                    att_rs.Close()
                except Exception as exc:
                    print(f"  [WARN] поле {acc_f!r}: {exc}")

            if imgs:
                result.append((name, imgs))
            rs.MoveNext()

        rs.Close()
    finally:
        db.Close()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 2 — Папка с файлами изображений
# ═══════════════════════════════════════════════════════════════════════════════

def _load_image_file(path: Path) -> bytes | None:
    try:
        data = path.read_bytes()
        return data if data else None
    except OSError as e:
        print(f"  [WARN] Не удалось прочитать {path}: {e}")
        return None


def extract_from_dir(images_dir: Path) -> list[tuple[str, dict[str, bytes]]]:
    """
    Сканирует папку с изображениями.
    Имя файла (без расширения) считается названием награды.
    Если имя содержит «_back» / «_оборот» / «оборот» — это image_back,
    иначе image_front.
    """
    if not images_dir.is_dir():
        print(f"Папка не найдена: {images_dir}")
        sys.exit(1)

    print(f"Сканирование: {images_dir}")
    result: list[tuple[str, dict[str, bytes]]] = []

    for f in sorted(images_dir.iterdir()):
        if f.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        stem = f.stem
        col = "image_back" if any(
            k in stem.lower() for k in ("_back", "_оборот", "оборот", "back")
        ) else "image_front"

        # Убираем суффикс _back/_front/_оборот из названия награды
        name = stem
        for sfx in ("_back", "_front", "_оборот", "_оборot", " оборот", " back", " front"):
            if name.lower().endswith(sfx):
                name = name[: len(name) - len(sfx)]
                break

        data = _load_image_file(f)
        if data:
            print(f"  {f.name} -> {col}  {_detect_fmt(data)} {len(data):,} bytes")
            result.append((name, {col: data}))

    # Слить дубли (одна награда — front + back)
    merged: dict[str, dict[str, bytes]] = {}
    for name, imgs in result:
        norm = _normalize(name)
        merged.setdefault(norm, (name, {}))
        merged[norm][1].update(imgs)

    return [(name, imgs) for name, imgs in merged.values()]


# ═══════════════════════════════════════════════════════════════════════════════
# РЕЖИМ 3 — CSV-таблица (ищем файлы по именам из колонок)
# ═══════════════════════════════════════════════════════════════════════════════

def _find_image_file(filename: str, search_dirs: list[Path]) -> Path | None:
    """Ищет файл по имени в нескольких папках (рекурсивно)."""
    fname = Path(filename).name  # отрезаем путь, если был
    for d in search_dirs:
        if not d.is_dir():
            continue
        # Точное совпадение
        p = d / fname
        if p.is_file():
            return p
        # Рекурсивный поиск
        found = list(d.rglob(fname))
        if found:
            return found[0]
        # Без учёта регистра
        found = [x for x in d.rglob("*") if x.name.lower() == fname.lower()]
        if found:
            return found[0]
    return None


def extract_from_csv(
    csv_dir: Path,
    search_dirs: list[Path],
) -> list[tuple[str, dict[str, bytes]]]:
    csv_path = csv_dir / "НаградыМега.csv"
    if not csv_path.is_file():
        # Попробуем найти по маске
        candidates = list(csv_dir.glob("*Награды*.csv"))
        if not candidates:
            print(f"CSV-файл не найден в {csv_dir}")
            sys.exit(1)
        csv_path = candidates[0]

    print(f"CSV: {csv_path}")
    result: list[tuple[str, dict[str, bytes]]] = []

    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            name = (row.get(NAME_FIELD) or row.get("Название награды") or "").strip()
            if not name:
                continue

            imgs: dict[str, bytes] = {}
            for csv_col in CSV_IMAGE_COLUMNS:
                if csv_col not in row:
                    continue
                fname = (row[csv_col] or "").strip()
                if not fname:
                    continue

                pg_col = "image_back" if any(
                    k in csv_col.lower() for k in ("оборот", "back")
                ) else "image_front"
                if pg_col in imgs:
                    continue

                img_path = _find_image_file(fname, search_dirs)
                if img_path is None:
                    print(f"  [MISS] «{name}» файл {fname!r} не найден")
                    continue
                data = _load_image_file(img_path)
                if data:
                    imgs[pg_col] = data
                    print(
                        f"  [CSV->{pg_col}] '{name}' "
                        f"{img_path.name} {_detect_fmt(data)} {len(data):,} bytes"
                    )

            if imgs:
                result.append((name, imgs))

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Миграция изображений наград в PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Из Access напрямую (требует Windows + pywin32):
  python migration/migrate_images.py --source access

  # Превью без записи:
  python migration/migrate_images.py --source access --dry-run

  # Статистика по Attachment-полям:
  python migration/migrate_images.py --source access --report

  # Из папки с картинками:
  python migration/migrate_images.py --source dir --images-dir C:/export/images

  # Из CSV-таблицы (имена файлов в колонках) + папка для поиска файлов:
  python migration/migrate_images.py --source csv --images-dir C:/export/images
        """,
    )
    p.add_argument(
        "--source", choices=["access", "dir", "csv"], default="access",
        help="Источник: access (DAO COM), dir (папка файлов), csv (CSV + папка)",
    )
    p.add_argument("--accdb", metavar="PATH", help="Путь к .accdb файлу")
    p.add_argument("--images-dir", metavar="PATH",
                   help="Папка с файлами изображений (для режимов dir и csv)")
    p.add_argument("--csv-dir", metavar="PATH",
                   default=str(ROOT / "migration" / "csv_export"),
                   help="Папка с CSV-выгрузкой (для режима csv)")
    p.add_argument("--dry-run", action="store_true",
                   help="Показать что будет сделано, без записи в БД")
    p.add_argument("--report", action="store_true",
                   help="Только статистика (только для --source access)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    dry_run = args.dry_run or os.environ.get("DRY_RUN", "").strip() in ("1", "true", "yes")

    # ── access ──
    if args.source == "access":
        accdb = _accdb_path(args.accdb)
        print(f"База Access: {accdb}")
        if args.report:
            run_access_report(accdb)
            return
        print(f"Режим: {'DRY RUN' if dry_run else 'ЗАПИСЬ в PostgreSQL'}\n")
        print("=== Извлечение из Access ===")
        extracted = extract_from_access(accdb)
        _save_images(extracted, dry_run)

    # ── dir ──
    elif args.source == "dir":
        if not args.images_dir:
            print("Укажите --images-dir ПУТЬ для режима dir")
            sys.exit(1)
        images_dir = Path(args.images_dir).expanduser().resolve()
        print(f"Режим: {'DRY RUN' if dry_run else 'ЗАПИСЬ в PostgreSQL'}\n")
        print("=== Сканирование папки ===")
        extracted = extract_from_dir(images_dir)
        _save_images(extracted, dry_run)

    # ── csv ──
    elif args.source == "csv":
        csv_dir = Path(args.csv_dir).expanduser().resolve()
        search_dirs: list[Path] = [csv_dir]
        if args.images_dir:
            search_dirs.insert(0, Path(args.images_dir).expanduser().resolve())
        # Рядом с .accdb тоже ищем
        try:
            accdb = _accdb_path(args.accdb)
            search_dirs.append(accdb.parent)
        except SystemExit:
            pass
        search_dirs.append(ROOT)

        print(f"Режим: {'DRY RUN' if dry_run else 'ЗАПИСЬ в PostgreSQL'}\n")
        print("=== Чтение из CSV ===")
        extracted = extract_from_csv(csv_dir, search_dirs)
        _save_images(extracted, dry_run)


if __name__ == "__main__":
    main()
