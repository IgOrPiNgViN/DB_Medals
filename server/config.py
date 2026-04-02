import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/awards_db")
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")

# Шаблон согласия на обработку ПД (DOCX).
# По умолчанию — файл в корне репозитория.
CONSENT_TEMPLATE_PATH = os.getenv(
    "CONSENT_TEMPLATE_PATH",
    os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "Согласие на обработку пер данных Награждения.docx",
        ),
    ),
)
