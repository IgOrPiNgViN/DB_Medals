"""Загрузка .env из корня репозитория в os.environ (без внешних зависимостей)."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse


def load_project_env(root: Path | None = None, *, override: bool = False) -> Path:
    root = root or Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    if not env_path.is_file():
        return env_path
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
    return env_path


def docker_database_url(root: Path | None = None) -> str:
    load_project_env(root, override=True)
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:changeme@localhost:5433/awards_db",
    )


def bootstrap_migration_env(root: Path | None = None) -> str:
    """Вызвать в migration/*.py до import database."""
    root = root or Path(__file__).resolve().parents[1]
    url = docker_database_url(root)
    os.environ["DATABASE_URL"] = url
    return url


def check_postgres(url: str) -> None:
    """Проверка доступности PostgreSQL до импорта."""
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        raise SystemExit(
            f"PostgreSQL недоступен на {host}:{port}.\n"
            "Запустите Docker:  .\\scripts\\start_docker_stack.ps1\n"
            f"({exc})"
        ) from exc

    try:
        import psycopg2

        psycopg2.connect(
            host=host,
            port=port,
            user=parsed.username or "postgres",
            password=parsed.password or "",
            dbname=(parsed.path or "/awards_db").lstrip("/"),
            connect_timeout=5,
        ).close()
    except UnicodeDecodeError as exc:
        raise SystemExit(
            "Ошибка подключения к PostgreSQL (неверный пароль или не тот сервер).\n"
            f"Используйте DATABASE_URL из .env: {url}\n"
            "Сбросьте переменную в терминале:  Remove-Item Env:DATABASE_URL\n"
            "Docker БД: порт 5433, пароль changeme. Локальная БД: порт 5432, пароль 1234."
        ) from exc
    except Exception as exc:
        raise SystemExit(
            f"Не удалось подключиться к PostgreSQL ({url}):\n{exc}\n"
            "Проверьте: docker compose ps  и  .\\scripts\\start_docker_stack.ps1"
        ) from exc
