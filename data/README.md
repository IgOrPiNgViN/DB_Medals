# Данные проекта (не код)

| Папка | Содержимое |
|-------|------------|
| `legacy/access/` | Базы Microsoft Access (`.accdb`, `.mdb`) — не в Git |
| `templates/` | Шаблоны документов (согласие на обработку ПД и т.п.) |
| `photos/` | Фотографии наград для `migration/import_photos.py` |

Переменные окружения:

- `ACCDB_PATH` — полный путь к нужному `.accdb` (если не в `legacy/access/`)
- `CONSENT_TEMPLATE_PATH` — шаблон DOCX (по умолчанию `templates/Согласие на обработку пер данных Награждения.docx`)
