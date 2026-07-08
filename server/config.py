import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES = _REPO_ROOT / "data" / "templates"


def _template_path(root_name: str, fallback_name: str) -> str:
    root_path = _REPO_ROOT / root_name
    if root_path.is_file():
        return str(root_path)
    return str(_TEMPLATES / fallback_name)

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
    _template_path("Бюллетень голосования - шаблон - 19-09-2024.docx", "Бюллетень голосования.docx"),
)
PROTOCOL_BRIEF_TEMPLATE_PATH = os.getenv(
    "PROTOCOL_BRIEF_TEMPLATE_PATH",
    _template_path("Протокол - шаблон - 22.06.2026.docx", "Протокол краткий.docx"),
)
PROTOCOL_FULL_TEMPLATE_PATH = os.getenv(
    "PROTOCOL_FULL_TEMPLATE_PATH",
    _template_path("Протокол - шаблон - 22.06.2026.docx", "Протокол подробный.docx"),
)
EXTRACT_MEDAL_TEMPLATE_PATH = os.getenv(
    "EXTRACT_MEDAL_TEMPLATE_PATH",
    _template_path(
        "Выписка из протокола - Медаль - шаблон 22-06-2026.docx",
        "Выписка из протокола — медаль.docx",
    ),
)
EXTRACT_PPZ_TEMPLATE_PATH = os.getenv(
    "EXTRACT_PPZ_TEMPLATE_PATH",
    _template_path(
        "Выписка из протокола -ППЗ - шаблон 22-06-2026.docx",
        "Выписка из протокола — ППЗ.docx",
    ),
)
PPZ_SUBMISSION_TEMPLATE_PATH = os.getenv(
    "PPZ_SUBMISSION_TEMPLATE_PATH",
    _template_path("Представление - шаблон - 22.06.2026.docx", "Представление ППЗ.docx"),
)
MONITORING_TEMPLATE_PATH = os.getenv(
    "MONITORING_TEMPLATE_PATH",
    str(_TEMPLATES / "Мониторинг ответов.docx"),
)
