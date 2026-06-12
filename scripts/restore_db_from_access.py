#!/usr/bin/env python3
"""
Полное восстановление PostgreSQL из выгрузки Access (CSV + фото).

Запуск из корня репозитория:
  python scripts/restore_db_from_access.py

Переменные окружения:
  DATABASE_URL — PostgreSQL (по умолчанию как у server/config.py)
  SKIP_NK_ACCESS=1 — не импортировать фото НК из .accdb (если файла нет)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_env import bootstrap_migration_env, check_postgres  # noqa: E402


def _run(label: str, cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
    print(f"\n=== {label} ===")
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(cwd), env=env)
    if r.returncode != 0:
        raise SystemExit(f"Ошибка: {label} (код {r.returncode})")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    db_url = bootstrap_migration_env(root)
    env = os.environ.copy()
    print(f"DATABASE_URL -> {db_url}")
    check_postgres(db_url)

    py = sys.executable
    skip_nk = os.getenv("SKIP_NK_ACCESS", "").strip().lower() in ("1", "true", "yes")

    steps: list[tuple[str, list[str]]] = [
        ("SQL-миграции схемы", [py, "migration/migrate_tz.py"]),
        ("Импорт CSV (данные Access)", [py, "migration/import_from_csv.py"]),
        ("Фото наград (data/photos)", [py, "migration/import_photos.py"]),
    ]
    if not skip_nk:
        steps.append(
            ("Фото членов НК (из Access backend)", [py, "migration/import_person_photos.py", "--from-access"]),
        )

    for label, cmd in steps:
        _run(label, cmd, root, env)

    print("\nГотово: БД в Docker восстановлена из CSV и фото.")
    print("Клиент: SERVER_URL=http://localhost:8000 (API в контейнере awards-api).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
