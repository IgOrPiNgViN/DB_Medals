"""
Загрузка фотографий из папки data/photos/ в PostgreSQL.
Маппинг составлен вручную по именам файлов и ID наград в БД.

Запуск:
  python migration/import_photos.py            # реальная запись
  python migration/import_photos.py --dry-run  # только просмотр
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
PHOTO_DIR = ROOT / "data" / "photos"

sys.path.insert(0, str(SERVER))
import os
os.chdir(SERVER)

from sqlalchemy.orm import Session  # noqa: E402
from database import SessionLocal   # noqa: E402
import models.award                 # noqa: F401, E402
from models.award import Award      # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Маппинг: award_id -> {front: имя_файла, back: имя_файла}
# Файлы с "Заглушка" / "Серия" / "Разработка" не используются как основные.
# ─────────────────────────────────────────────────────────────────────────────
MAPPING: dict[int, dict[str, str]] = {
    # --- без отдельного файла в CSV / только в БД — привязка к Фото/ ---
    # id 1: в выгрузке нет имени файла; визуально близкая серия «динамика развития»
    1: {"front": "МедальДинамикаРазвития.png"},
    # id 15: тестовый ППЗ — заглушка из той же папки
    15: {"front": "ЗаглушкаППЗ.png"},
    # id 17, 19, 20: формулировки СВО без отдельных сканов — тот же комплект, что «Медаль V» (боевые задачи)
    17: {"front": "МедальV.png", "back": "МедальVРеверс.png"},
    19: {"front": "МедальV.png", "back": "МедальVРеверс.png"},
    20: {"front": "МедальV.png", "back": "МедальVРеверс.png"},
    # Медали Грайфера I / II / III
    2:  {"front": "МедальГрайфера1.png",    "back": "МедальГрайфера1Реверс.png"},
    3:  {"front": "МедальГрайфера2.png",    "back": "МедальГрайфера2Реверс.png"},
    4:  {"front": "МедальГрайфера3.png",    "back": "МедальГрайфера3Реверс.png"},
    # Медаль Лемаева
    5:  {"front": "МедальЛемаева.png",      "back": "МедальЛемаеваРеверс.png"},
    # Медаль Михельсона (оборота нет в папке)
    6:  {"front": "МедальМихельсона.png"},
    # Медаль Непорожнего (Заглушка — пустая, берём только основную)
    7:  {"front": "МедальНепорожнего.png"},
    # Медаль Оруджева (Картинка = рендер, Фото = скан; берём Фото + оборот)
    8:  {"front": "МедальОруджеваФото.png", "back": "МедальОруджеваРеверс.png"},
    # Медаль Трофимука
    9:  {"front": "МедальТрофимука.png"},
    # Медаль Хаджиева (Фото + оборот; перезапишет картинку из Access)
    10: {"front": "МедальХаджиеваФото.png", "back": "МедальХаджиеваРеверс.png"},
    # ППЗ Грайфера
    11: {"front": "ППЗГрайфера.png",        "back": "ППЗГрайфераРеверс.png"},
    # ППЗ за освоение недр ЗС
    12: {"front": "ППЗЗаОсвоениеНедрЗС.png"},
    # ППЗ Михельсона
    13: {"front": "ППЗМихельсона.png",      "back": "ППЗМихельсонаРеверс.png"},
    # ППЗ Оруджева
    14: {"front": "ППЗОруджева.png"},
    # Медаль V (СВО) — боевые задачи в условиях СВО
    16: {"front": "МедальV.png",            "back": "МедальVРеверс.png"},
    # Медаль Z (оборот; аверс уже загружен из Access — перезапишем качественнее)
    18: {"front": "МедальZ.png",            "back": "МедальZРеверс.png"},
    # Медаль Голубкова
    21: {"front": "МедальГолубкова.png"},
    # Голубкова С.В. (та же медаль, дубль записи в БД)
    22: {"front": "МедальГолубкова.png"},
    # Маганова Р.У. — тип PPZ
    23: {"front": "ППЗМаганова.png",        "back": "ППЗМагановаРеверс.png"},
    # ППЗ Конторовича (перезапишет картинку из Access)
    24: {"front": "ППЗКонторовича.png",     "back": "ППЗКонторовичаРеверс.png"},
}

# Файлы в папке, которые НЕ имеют соответствия в текущей БД
UNMATCHED_FILES = [
    "ДинамикаРазвитияСерия.png",
    "ДинамикаРазвитияСерия большая.png",
    "ЗаглушкаМедаль.png",
    "ЗОЛучшийМолодойСпецалист.png",
    "ЗОЛучшийМолодойСпецалист2.png",
    "ЗОЛучшийНаставник.png",
    "ЗОЛучшийНаставник2.png",
    "ЗОЛучшийПоПрофессии.png",
    "ЗОЛучшийПоПрофессии2.png",
    "ЗОНоватор.png",
    "ЗОНоватор2.png",
    "ЛидерыРостаСерия.png",
    "МедальВиноградова.png",
    "МедальВиноградовЗаглушка.png",
    "МедальВяхирева.png",
    "МедальГрайфераСерия.png",
    "МедальДинамикаРазвимтияРазработка.png",
    "МедальДинамикаРазвитияАверсЗаглушка.png",
    "МедальЗернова.png",
    "МедальЗерноваЗаглушка.png",
    "МедальЗерноваРеверс.png",
    "МедальКарбышева.png",
    "МедальКарбышеваЗаглушка.png",
    "МедальКарбышеваРеверс.png",
    "МедальЛидерыРоста.png",
    "МедальМаганова.png",     # медаль; в БД Маганова — ППЗ (id=23)
    "МедальМатлашов.png",
    "МедальМатлашовЗаглушка.png",
    "МедальНепорожнегоЗаглушка.png",
    "МедальОруджеваКартинка.png",
    "МедальРазумовЗаглушка.png",
    "МедальРаумова.png",
    "МедальСтаровойтова.png",
    "МедальСтаровойтоваЗаглушка.png",
    "МедальСтаровойтоваРеверс.png",
    "МедальТрофимукаЗаглушка.png",
    "МедальХаджиеваКартинка.png",
    "МедальХаджиеваРисунок.png",
    "МедальШашина.png",
    "МедальШашинаРазработка.png",
    "ППЗЛемаева уменьшенный.png",
    "ППЗЛемаева.png",
    "ППЗЛемаеваРеверс.png",
    "ППЗМагановаРеверс.png",  # back — в mapping уже есть
]


def _detect_fmt(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if data[:2] == b"\xff\xd8":
        return "JPEG"
    return "?"


def run(dry_run: bool) -> None:
    if not PHOTO_DIR.is_dir():
        print(f"Папка не найдена: {PHOTO_DIR}")
        sys.exit(1)

    print(f"Папка с фото: {PHOTO_DIR}")
    print(f"Режим: {'DRY RUN (запись отключена)' if dry_run else 'ЗАПИСЬ в PostgreSQL'}")
    print()

    # Проверим наличие файлов
    missing = []
    plan: list[tuple[int, str, bytes, str]] = []  # (award_id, col, data, filename)

    for award_id, sides in sorted(MAPPING.items()):
        for side, filename in sides.items():
            col = "image_front" if side == "front" else "image_back"
            path = PHOTO_DIR / filename
            if not path.exists():
                missing.append(f"  id={award_id} [{side}]: {filename} — ФАЙЛ НЕ НАЙДЕН")
                continue
            data = path.read_bytes()
            plan.append((award_id, col, data, filename))

    if missing:
        print("=== ОТСУТСТВУЮЩИЕ ФАЙЛЫ ===")
        for m in missing:
            print(m)
        print()

    print(f"=== ПЛАН ЗАГРУЗКИ ({len(plan)} файлов) ===")
    for award_id, col, data, fn in plan:
        fmt = _detect_fmt(data)
        side_label = "лицо  " if col == "image_front" else "оборот"
        print(f"  id={award_id:2d}  {side_label}  {fmt}  {len(data):>7,} bytes  <- {fn}")

    print()
    print("=== ФАЙЛЫ БЕЗ НАГРАДЫ В БД (не импортируются) ===")
    print("  (это награды не внесённые в БД — можно добавить вручную)")
    no_match = set(f.name for f in PHOTO_DIR.iterdir()) - \
               {fn for _, sides in MAPPING.items() for fn in sides.values()} - \
               set(UNMATCHED_FILES)
    all_skip = set(UNMATCHED_FILES) | no_match
    # filter to what's actually in the folder
    in_folder = {f.name for f in PHOTO_DIR.iterdir()}
    shown = sorted(all_skip & in_folder)
    for fn in shown:
        size = (PHOTO_DIR / fn).stat().st_size // 1024
        print(f"  {fn}  ({size} KB)")

    if dry_run:
        print("\nDRY RUN завершён. Для записи запустите без --dry-run.")
        return

    print("\n=== ЗАПИСЬ В POSTGRESQL ===")
    pg: Session = SessionLocal()
    updated = skipped = 0
    try:
        for award_id, col, data, fn in plan:
            award = pg.query(Award).filter(Award.id == award_id).first()
            if award is None:
                print(f"  [MISS] id={award_id} не найден в БД")
                continue
            existing = getattr(award, col)
            if existing and len(bytes(existing)) == len(data):
                print(f"  [SKIP] id={award_id} {col} уже такой же размер ({len(data):,} bytes)")
                skipped += 1
                continue
            setattr(award, col, data)
            fmt = _detect_fmt(data)
            print(f"  [SAVE] id={award_id}  {col}  {fmt}  {len(data):,} bytes  <- {fn}")
            updated += 1
        pg.commit()
    except Exception as exc:
        pg.rollback()
        print(f"Ошибка: {exc}")
        raise
    finally:
        pg.close()

    print(f"\nЗаписано: {updated}  |  Пропущено: {skipped}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--list-awards",
        action="store_true",
        help="Показать id и названия наград в БД (для сверки с MAPPING)",
    )
    args = p.parse_args()
    if args.list_awards:
        _print_awards_from_db()
        return
    run(args.dry_run)


def _print_awards_from_db() -> None:
    pg: Session = SessionLocal()
    try:
        rows = pg.query(Award).order_by(Award.id).all()
        if not rows:
            print("В таблице awards нет строк.")
            return
        print("id\tname")
        for a in rows:
            name = (a.name or "").replace("\n", " ").replace("\t", " ")[:200]
            print(f"{a.id}\t{name}")
        print(f"\nВсего: {len(rows)}")
    finally:
        pg.close()


if __name__ == "__main__":
    main()
