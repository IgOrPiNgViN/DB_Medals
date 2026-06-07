"""Применить SQL-миграции из migration/*.sql."""
from db_migrations import (
    ensure_consent_pd_schema,
    ensure_tz_lc_schema,
    ensure_tz_full_schema,
    ensure_tz_committee_extra,
    ensure_kit_disposals_schema,
    ensure_production_stages_schema,
)
from database import engine


def apply_migrations() -> None:
    ensure_tz_lc_schema(engine)
    ensure_tz_full_schema(engine)
    ensure_tz_committee_extra(engine)
    ensure_consent_pd_schema(engine)
    ensure_kit_disposals_schema(engine)
    ensure_production_stages_schema(engine)


if __name__ == "__main__":
    apply_migrations()
    print("migrations applied")
