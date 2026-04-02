from __future__ import annotations

from sqlalchemy import Engine, text


def _safe_exec(engine: Engine, sql: str) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except Exception:
        # БД может быть не Postgres или колонка уже есть — не валим запуск.
        pass


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
