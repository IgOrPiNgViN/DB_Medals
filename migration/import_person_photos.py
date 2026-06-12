"""
Импорт фотографий лауреатов и членов НК по именам файлов из CSV.

Файлы ищутся в (по порядку):
  - data/photos/persons/
  - data/photos/nk/
  - data/photos/
  - migration/extracted_images/

Запуск из корня репозитория:
  python migration/import_person_photos.py --from-access   # рекомендуется для НК
  python migration/import_person_photos.py
  python migration/import_person_photos.py --dry-run

Фото НК хранятся в Access (не в папках). Скрипт extract_nk_photos_from_access.py
читает backend *_be.accdb и пишет в PostgreSQL или data/photos/nk/.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
CSV_DIR = ROOT / "migration" / "csv_export"

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(SERVER))
import os
from load_env import bootstrap_migration_env  # noqa: E402

bootstrap_migration_env(ROOT)
os.chdir(SERVER)

from sqlalchemy.orm import Session  # noqa: E402
from database import SessionLocal  # noqa: E402
import models.committee  # noqa: F401, E402
import models.laureate  # noqa: F401, E402
from models.committee import CommitteeMember  # noqa: E402
from models.laureate import Laureate  # noqa: E402


def _search_dirs() -> list[Path]:
    return [
        ROOT / "data" / "photos" / "persons",
        ROOT / "data" / "photos" / "nk",
        ROOT / "data" / "photos",
        ROOT / "migration" / "extracted_images",
    ]


def _find_file(name: str) -> Path | None:
    raw = (name or "").strip()
    if not raw:
        return None
    candidates = [raw]
    if not raw.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
        candidates.extend([raw + ext for ext in (".jpg", ".jpeg", ".png", ".JPG", ".PNG")])
    for d in _search_dirs():
        if not d.is_dir():
            continue
        for cand in candidates:
            p = d / cand
            if p.is_file():
                return p
        # case-insensitive fallback
        lower_map = {f.name.lower(): f for f in d.iterdir() if f.is_file()}
        for cand in candidates:
            hit = lower_map.get(cand.lower())
            if hit:
                return hit
    return None


def _read_nk_csv() -> list[tuple[str, str]]:
    path = CSV_DIR / "Список НК.csv"
    if not path.is_file():
        return []
    import csv
    rows: list[tuple[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            fn = (row.get("ФИО") or "").strip()
            photo = (row.get("Фото") or "").strip()
            if fn and photo:
                rows.append((fn, photo))
    return rows


def _read_laureate_csv() -> list[tuple[str, str]]:
    path = CSV_DIR / "Лауреаты.csv"
    if not path.is_file():
        return []
    import csv
    rows: list[tuple[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        photo_col = None
        for col in (reader.fieldnames or []):
            if "фото" in col.lower():
                photo_col = col
                break
        if not photo_col:
            return []
        for row in reader:
            fn = (row.get("ФИО") or "").strip()
            photo = (row.get(photo_col) or "").strip()
            if fn and photo:
                rows.append((fn, photo))
    return rows


def _norm_name(s: str) -> str:
    return " ".join((s or "").split()).lower()


def run(dry_run: bool, skip_nk: bool = False) -> None:
    nk_rows = [] if skip_nk else _read_nk_csv()
    la_rows = _read_laureate_csv()
    if not skip_nk:
        print(f"CSV: НК с фото — {len(_read_nk_csv())}, лауреаты с фото — {len(la_rows)}")
    else:
        print(f"CSV: лауреаты с фото — {len(la_rows)} (НК уже загружены из Access)")
    print("Папки поиска:")
    for d in _search_dirs():
        print(f"  {'[OK]' if d.is_dir() else '[—]'} {d}")

    db: Session = SessionLocal()
    nk_saved = nk_miss = la_saved = la_miss = 0
    try:
        members = { _norm_name(m.full_name): m for m in db.query(CommitteeMember).all() }
        laureates = { _norm_name(l.full_name): l for l in db.query(Laureate).all() }

        for full_name, filename in nk_rows:
            path = _find_file(filename)
            member = members.get(_norm_name(full_name))
            if member is None:
                print(f"  [SKIP NK] нет в БД: {full_name}")
                continue
            if path is None:
                nk_miss += 1
                print(f"  [MISS NK] {full_name} <- {filename}")
                continue
            data = path.read_bytes()
            if dry_run:
                print(f"  [DRY NK] {full_name} <- {path.name} ({len(data)} bytes)")
            else:
                member.photo = data
                member.photo_filename = path.name
                nk_saved += 1
                print(f"  [SAVE NK] {full_name} <- {path.name}")

        for full_name, filename in la_rows:
            path = _find_file(filename)
            laureate = laureates.get(_norm_name(full_name))
            if laureate is None:
                print(f"  [SKIP LA] нет в БД: {full_name}")
                continue
            if path is None:
                la_miss += 1
                print(f"  [MISS LA] {full_name} <- {filename}")
                continue
            data = path.read_bytes()
            if dry_run:
                print(f"  [DRY LA] {full_name} <- {path.name} ({len(data)} bytes)")
            else:
                laureate.photo = data
                la_saved += 1
                print(f"  [SAVE LA] {full_name} <- {path.name}")

        if not dry_run:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(
        f"\nИтог: НК сохранено {nk_saved}, не найдено файлов {nk_miss}; "
        f"лауреаты сохранено {la_saved}, не найдено {la_miss}"
    )
    if nk_miss or la_miss:
        print(
            "Подсказка: для НК используйте --from-access (фото в backend Access):\n"
            "  python migration/import_person_photos.py --from-access"
        )


def _run_from_access(dry_run: bool) -> None:
    script = ROOT / "migration" / "extract_nk_photos_from_access.py"
    cmd = [sys.executable, str(script)]
    if dry_run:
        cmd.append("--dry-run")
    print("=== Импорт фото НК из Access ===")
    subprocess.run(cmd, check=True)
    if not dry_run:
        run(dry_run=False, skip_nk=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--from-access",
        action="store_true",
        help="Извлечь фото НК из backend Access (*_be.accdb)",
    )
    args = p.parse_args()
    if args.from_access:
        _run_from_access(args.dry_run)
    else:
        run(args.dry_run)


if __name__ == "__main__":
    main()
