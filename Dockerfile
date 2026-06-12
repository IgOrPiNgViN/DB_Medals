# Сборка образа API (FastAPI + Uvicorn). Контекст сборки — корень репозитория.
FROM python:3.11-slim-bookworm

# pg_dump/pg_restore той же мажорной версии, что и postgres:16-alpine в compose.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY server/ /app/server/

# Минимальный DOCX для пути CONSENT_TEMPLATE_PATH (python-docx уже в requirements).
# Реальный шаблон согласия при необходимости подмените томом — см. README (Docker).
RUN mkdir -p /app/templates \
    && python -c "from docx import Document; Document().save('/app/templates/consent.docx')"

WORKDIR /app/server

ENV PYTHONUNBUFFERED=1 \
    CONSENT_TEMPLATE_PATH=/app/templates/consent.docx \
    BACKUP_DIR=/app/server/backups

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
