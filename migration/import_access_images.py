"""
Извлечение изображений из поля Attachment (type=101) таблицы НаградыМега
в базе данных Microsoft Access и загрузка их в PostgreSQL (колонка image_front).

Требования:
  - Windows с установленным Microsoft Access (или Access Runtime)
  - pip install pywin32

Запуск:
  cd "<корень проекта>"
  python migration/import_access_images.py

Переменные окружения:
  ACCDB_PATH   — путь к файлу .accdb (по умолчанию data/legacy/access/)
  DATABASE_URL — строка подключения PostgreSQL (как у сервера)
  DRY_RUN=1    — только показать, что будет сделано, без записи в БД
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
sys.path.insert(0, str(SERVER))

# Разрешаем ACCDB_PATH до смены рабочей директории
_ACCDB_ENV_RAW = os.environ.get("ACCDB_PATH", "").strip()
if _ACCDB_ENV_RAW:
    _accdb_resolved = str(Path(_ACCDB_ENV_RAW).expanduser().resolve())
    os.environ["ACCDB_PATH"] = _accdb_resolved

os.chdir(SERVER)

try:
    import win32com.client as w32
except ImportError:
    print("Установите: pip install pywin32")
    sys.exit(1)

from sqlalchemy.orm import Session  # noqa: E402
from database import SessionLocal  # noqa: E402
import models.award  # noqa: F401, E402
from models.award import Award  # noqa: E402


# ──────────────────────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────────────────────

# Поля Attachment в НаградыМега, из которых берём изображение (по приоритету)
ATTACHMENT_FIELDS = [
    "Изображение",
    "Файл_протокол",
]

# Таблица Access
ACCESS_TABLE = "НаградыМега"

# Поле с названием награды (ключ связки с PostgreSQL)
NAME_FIELD = "Название награды"

# DAO field type 101 = Attachment
DAO_TYPE_ATTACHMENT = 101


# ──────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────

def _accdb_path() -> Path:
    env = os.environ.get("ACCDB_PATH", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_file():
            return p
        print(f"[WARN] ACCDB_PATH не найден: {p}")

    # Ищем бэкенд-файл в data/legacy/access/ (файл без «архив» в имени)
    legacy_dir = ROOT / "data" / "legacy" / "access"
    candidates = sorted(legacy_dir.glob("*.accdb")) if legacy_dir.is_dir() else []
    if not candidates:
        candidates = sorted(ROOT.glob("*.accdb"))
    for c in candidates:
        if "архив" not in c.name.lower():
            return c
    if candidates:
        return candidates[0]

    print("Ошибка: файл .accdb не найден. Укажите ACCDB_PATH.")
    sys.exit(1)


def _parse_attachment_data(raw: bytes) -> bytes:
    """
    Формат Access Attachment FileData:
      Байты 0-3 (uint32 LE): размер заголовка (N)
      Байты N+: сами данные файла
    """
    if len(raw) < 4:
        return raw
    header_size = struct.unpack_from("<I", raw, 0)[0]
    return raw[header_size:]


def _open_access_db(accdb: Path):
    engine = w32.Dispatch("DAO.DBEngine.120")
    db = engine.OpenDatabase(str(accdb))
    return db


def _is_attachment_field(table_def, field_name: str) -> bool:
    for f in table_def.Fields:
        if f.Name == field_name:
            return f.Type == DAO_TYPE_ATTACHMENT
    return False


def _extract_images_from_access(accdb: Path) -> dict[str, bytes]:
    """
    Возвращает словарь {название_награды: bytes_изображения}.
    Берёт первый непустой Attachment из ATTACHMENT_FIELDS.
    """
    db = _open_access_db(accdb)
    result: dict[str, bytes] = {}

    # Узнаём, какие поля реально Attachment
    tdef = None
    for t in db.TableDefs:
        if t.Name == ACCESS_TABLE:
            tdef = t
            break
    if tdef is None:
        print(f"Таблица '{ACCESS_TABLE}' не найдена в {accdb.name}")
        db.Close()
        return result

    attachment_fields = [
        f for f in ATTACHMENT_FIELDS
        if _is_attachment_field(tdef, f)
    ]
    if not attachment_fields:
        print(f"Attachment-поля не найдены в {ACCESS_TABLE}")
        db.Close()
        return result

    print(f"Attachment-поля: {attachment_fields}")

    rs = db.OpenRecordset(ACCESS_TABLE)
    rs.MoveFirst()
    while not rs.EOF:
        award_name = rs.Fields(NAME_FIELD).Value
        if not award_name:
            rs.MoveNext()
            continue

        for field_name in attachment_fields:
            try:
                att_rs = rs.Fields(field_name).Value
                # BOF+EOF — единственный надёжный способ проверить пустой
                # dynaset-рекордсет DAO (RecordCount может вернуть -1)
                if att_rs.BOF and att_rs.EOF:
                    att_rs.Close()
                    continue
                att_rs.MoveFirst()
                while not att_rs.EOF:
                    raw = att_rs.Fields("FileData").Value
                    if raw:
                        img_bytes = _parse_attachment_data(bytes(raw))
                        if img_bytes:
                            result[award_name] = img_bytes
                            fname = att_rs.Fields("FileName").Value
                            print(
                                f"  [OK] «{award_name}» → {fname} "
                                f"({len(img_bytes):,} байт)"
                            )
                            break
                    att_rs.MoveNext()
                att_rs.Close()
                if award_name in result:
                    break  # нашли для этой награды, переходим к следующей
            except Exception:
                pass

        rs.MoveNext()

    rs.Close()
    db.Close()
    return result


def _find_award_by_name(db: Session, name: str) -> Award | None:
    """Точное совпадение, затем вхождение."""
    award = db.query(Award).filter(Award.name == name).first()
    if award:
        return award
    # Нечёткий поиск: ищем по вхождению (в обе стороны)
    awards = db.query(Award).all()
    name_lower = name.lower()
    for a in awards:
        if a.name.lower() in name_lower or name_lower in a.name.lower():
            return a
    return None


# ──────────────────────────────────────────────────────────────
# Основная логика
# ──────────────────────────────────────────────────────────────

def main() -> None:
    dry_run = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "yes")
    accdb = _accdb_path()

    print(f"База Access : {accdb}")
    print(f"Режим       : {'DRY RUN (без записи в БД)' if dry_run else 'ЗАПИСЬ в PostgreSQL'}")
    print()

    # 1. Читаем изображения из Access
    print("=== Извлечение изображений из Access ===")
    images = _extract_images_from_access(accdb)
    if not images:
        print("Изображения не найдены — нечего импортировать.")
        return

    print(f"\nНайдено изображений: {len(images)}")
    print()

    if dry_run:
        print("DRY RUN — выход.")
        return

    # 2. Загружаем в PostgreSQL
    print("=== Загрузка в PostgreSQL ===")
    db: Session = SessionLocal()
    try:
        updated = 0
        not_found = []
        for access_name, img_bytes in images.items():
            award = _find_award_by_name(db, access_name)
            if award is None:
                not_found.append(access_name)
                print(f"  [SKIP] «{access_name}» — награда не найдена в PostgreSQL")
                continue
            award.image_front = img_bytes
            print(
                f"  [SAVE] «{access_name}» → Award id={award.id} «{award.name}» "
                f"({len(img_bytes):,} байт)"
            )
            updated += 1

        db.commit()
        print(f"\nОбновлено записей: {updated}")
        if not_found:
            print(
                f"Не найдены в PostgreSQL ({len(not_found)}): "
                + ", ".join(f'«{n}»' for n in not_found)
            )
    except Exception as exc:
        db.rollback()
        print(f"Ошибка при записи: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
