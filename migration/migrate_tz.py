"""
Применить SQL-миграции из migration/*.sql.

Запуск из корня репозитория:
    python migration/migrate_tz.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(SERVER))
from load_env import bootstrap_migration_env, check_postgres  # noqa: E402

bootstrap_migration_env(ROOT)
os.chdir(SERVER)

from db_migrations import (  # noqa: E402
    ensure_consent_pd_schema,
    ensure_tz_lc_schema,
    ensure_tz_full_schema,
    ensure_tz_committee_extra,
    ensure_kit_disposals_schema,
    ensure_production_stages_schema,
)
from database import engine  # noqa: E402


def apply_migrations() -> None:
    ensure_tz_lc_schema(engine)
    ensure_tz_full_schema(engine)
    ensure_tz_committee_extra(engine)
    ensure_consent_pd_schema(engine)
    ensure_kit_disposals_schema(engine)
    ensure_production_stages_schema(engine)


if __name__ == "__main__":
    check_postgres(os.environ["DATABASE_URL"])
    apply_migrations()
    print("migrations applied")
