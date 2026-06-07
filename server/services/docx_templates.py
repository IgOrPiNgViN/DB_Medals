"""Загрузка организационных Word-шаблонов и подстановка плейсхолдеров {{KEY}}."""

import os
import re
from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi import HTTPException

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def replace_placeholders(doc: Document, mapping: dict[str, str]) -> None:
    def apply_paragraphs(paragraphs):
        for p in paragraphs:
            if "{{" not in p.text:
                continue
            for run in p.runs:
                text = run.text
                for m in _PLACEHOLDER.finditer(text):
                    key = m.group(1)
                    text = text.replace(m.group(0), mapping.get(key, "—"))
                run.text = text

    apply_paragraphs(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                apply_paragraphs(cell.paragraphs)


def load_template_or_raise(path: str, label: str) -> Document:
    if not path or not os.path.isfile(path):
        raise HTTPException(
            status_code=500,
            detail=f"Шаблон «{label}» не найден: {path}. Запустите: python scripts/build_doc_templates.py",
        )
    return Document(path)


def render_template(path: str, label: str, mapping: dict[str, str]) -> bytes:
    doc = load_template_or_raise(path, label)
    replace_placeholders(doc, mapping)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def ensure_parent_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def write_minimal_template(path: str, title: str, placeholders: list[str]) -> None:
    """Создать простой шаблон с плейсхолдерами (если файла ещё нет)."""
    if os.path.isfile(path):
        return
    ensure_parent_dir(path)
    doc = Document()
    doc.add_heading(title, level=1)
    for ph in placeholders:
        doc.add_paragraph(f"{{{{{ph}}}}}")
    doc.save(path)
