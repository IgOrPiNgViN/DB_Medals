import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONSENT_TEMPLATE = (
    _REPO_ROOT / "data" / "templates" / "Согласие на обработку пер данных Награждения.docx"
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/awards_db")
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")

# Шаблон согласия на обработку ПД (DOCX) — data/templates/
CONSENT_TEMPLATE_PATH = os.getenv(
    "CONSENT_TEMPLATE_PATH",
    str(_DEFAULT_CONSENT_TEMPLATE),
)
