import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES = _REPO_ROOT / "data" / "templates"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/awards_db")
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")

CONSENT_TEMPLATE_PATH = os.getenv(
    "CONSENT_TEMPLATE_PATH",
    str(_TEMPLATES / "Согласие на обработку пер данных Награждения.docx"),
)
CERTIFICATE_TEMPLATE_PATH = os.getenv(
    "CERTIFICATE_TEMPLATE_PATH",
    str(_TEMPLATES / "Удостоверение к награде.docx"),
)
BULLETIN_TEMPLATE_PATH = os.getenv(
    "BULLETIN_TEMPLATE_PATH",
    str(_TEMPLATES / "Бюллетень голосования.docx"),
)
PROTOCOL_BRIEF_TEMPLATE_PATH = os.getenv(
    "PROTOCOL_BRIEF_TEMPLATE_PATH",
    str(_TEMPLATES / "Протокол краткий.docx"),
)
PROTOCOL_FULL_TEMPLATE_PATH = os.getenv(
    "PROTOCOL_FULL_TEMPLATE_PATH",
    str(_TEMPLATES / "Протокол подробный.docx"),
)
EXTRACT_MEDAL_TEMPLATE_PATH = os.getenv(
    "EXTRACT_MEDAL_TEMPLATE_PATH",
    str(_TEMPLATES / "Выписка из протокола — медаль.docx"),
)
EXTRACT_PPZ_TEMPLATE_PATH = os.getenv(
    "EXTRACT_PPZ_TEMPLATE_PATH",
    str(_TEMPLATES / "Выписка из протокола — ППЗ.docx"),
)
PPZ_SUBMISSION_TEMPLATE_PATH = os.getenv(
    "PPZ_SUBMISSION_TEMPLATE_PATH",
    str(_TEMPLATES / "Представление ППЗ.docx"),
)
MONITORING_TEMPLATE_PATH = os.getenv(
    "MONITORING_TEMPLATE_PATH",
    str(_TEMPLATES / "Мониторинг ответов.docx"),
)
