from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, text


def _safe_exec(engine: Engine, sql: str) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except Exception:
        # БД может быть не Postgres или колонка уже есть — не валим запуск.
        pass


def ensure_tz_full_schema(engine: Engine) -> None:
    """Поля лауреата, НК, учреждение, комплекты, украшения."""
    dialect = getattr(engine, "dialect", None)
    if getattr(dialect, "name", "") != "postgresql":
        return
    mig = Path(__file__).resolve().parent.parent / "migration" / "add_tz_full_fields.sql"
    if not mig.is_file():
        return
    for line in mig.read_text(encoding="utf-8").splitlines():
        stmt = line.strip()
        if stmt and not stmt.startswith("--"):
            _safe_exec(engine, stmt)


def ensure_tz_committee_extra(engine: Engine) -> None:
    dialect = getattr(engine, "dialect", None)
    if getattr(dialect, "name", "") != "postgresql":
        return
    mig = Path(__file__).resolve().parent.parent / "migration" / "add_tz_committee_extra.sql"
    if not mig.is_file():
        return
    for line in mig.read_text(encoding="utf-8").splitlines():
        stmt = line.strip()
        if stmt and not stmt.startswith("--"):
            _safe_exec(engine, stmt)


def ensure_tz_lc_schema(engine: Engine) -> None:
    """Поля ЖЦ лауреата по ТЗ (Access: ЛАУР_ЖЦ.csv)."""
    dialect = getattr(engine, "dialect", None)
    if getattr(dialect, "name", "") != "postgresql":
        return
    mig = Path(__file__).resolve().parent.parent / "migration" / "add_tz_lc_fields.sql"
    if not mig.is_file():
        return
    for line in mig.read_text(encoding="utf-8").splitlines():
        stmt = line.strip()
        if stmt and not stmt.startswith("--"):
            _safe_exec(engine, stmt)


def ensure_consent_pd_schema(engine: Engine) -> None:
    """
    create_all() не добавляет колонки в существующие таблицы.
    Поэтому аккуратно добавляем нужные поля для «Согласие ПД» в ЖЦ лауреата.
    """
    dialect = getattr(engine, "dialect", None)
    name = getattr(dialect, "name", "")

    # Postgres: поддерживает ADD COLUMN IF NOT EXISTS
    if name == "postgresql":
        _safe_exec(
            engine,
            """
            ALTER TABLE laureate_lifecycles
              ADD COLUMN IF NOT EXISTS consent_sent_date DATE;
            """,
        )
        _safe_exec(
            engine,
            """
            ALTER TABLE laureate_lifecycles
              ADD COLUMN IF NOT EXISTS consent_received_date DATE;
            """,
        )
        _safe_exec(
            engine,
            """
            ALTER TABLE laureate_lifecycles
              ADD COLUMN IF NOT EXISTS consent_received BOOLEAN DEFAULT FALSE;
            """,
        )
        return

    # Для других диалектов пытаемся без IF NOT EXISTS (с проглатыванием ошибки).
    _safe_exec(engine, "ALTER TABLE laureate_lifecycles ADD COLUMN consent_sent_date DATE;")
    _safe_exec(engine, "ALTER TABLE laureate_lifecycles ADD COLUMN consent_received_date DATE;")
    _safe_exec(engine, "ALTER TABLE laureate_lifecycles ADD COLUMN consent_received BOOLEAN;")


def ensure_kit_disposals_schema(engine: Engine) -> None:
    """Журнал выбытия комплектов и универсальный склад (ТЗ file-012)."""
    dialect = getattr(engine, "dialect", None)
    if getattr(dialect, "name", "") != "postgresql":
        return
    mig = Path(__file__).resolve().parent.parent / "migration" / "add_kit_disposals.sql"
    if not mig.is_file():
        return
    for line in mig.read_text(encoding="utf-8").splitlines():
        stmt = line.strip()
        if stmt and not stmt.startswith("--"):
            _safe_exec(engine, stmt)


def ensure_production_stages_schema(engine: Engine) -> None:
    """10 этапов производства на компонент (ТЗ file-008)."""
    dialect = getattr(engine, "dialect", None)
    if getattr(dialect, "name", "") != "postgresql":
        return
    for mig_name in ("add_production_stages.sql", "add_production_stage_attachments.sql"):
        mig = Path(__file__).resolve().parent.parent / "migration" / mig_name
        if not mig.is_file():
            continue
        for line in mig.read_text(encoding="utf-8").splitlines():
            stmt = line.strip()
            if stmt and not stmt.startswith("--"):
                _safe_exec(engine, stmt)
