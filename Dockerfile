# Сборка образа API (FastAPI + Uvicorn). Контекст сборки — корень репозитория.
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
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
