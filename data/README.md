# Данные проекта (не код)

| Папка | Содержимое |
|-------|------------|
| `legacy/access/` | Базы Microsoft Access (`.accdb`, `.mdb`) — не в Git |
| `templates/` | Шаблоны документов (согласие на обработку ПД и т.п.) |
| `photos/` | Фотографии наград для `migration/import_photos.py` |
| `photos/nk/` | Фото членов НК (или извлекаются из Access) |

Импорт людей:
```powershell
python migration/import_person_photos.py --from-access
```
Фото НК лежат в backend Access (`data/legacy/access/*_be.accdb`), не в папках.

Переменные окружения:

- `ACCDB_PATH` — полный путь к нужному `.accdb` (если не в `legacy/access/`)
- `ACCDB_BACKEND` — backend `*_be.accdb` для извлечения вложений (фото НК)
- `CONSENT_TEMPLATE_PATH` — шаблон DOCX (по умолчанию `templates/Согласие на обработку пер данных Награждения.docx`)

Фирменные DOCX: замените файлы в `templates/` или `python scripts/build_doc_templates.py --list` / `--rebuild`.
