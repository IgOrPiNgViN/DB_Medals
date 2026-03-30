"""Печать, PDF и экспорт HTML (для открытия в Microsoft Word) из HTML или QTableWidget."""

from __future__ import annotations

import html as html_module
from pathlib import Path
from typing import Optional

from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtWidgets import QFileDialog, QTableWidget, QWidget


def qtable_widget_to_html(table: QTableWidget, title: str = "") -> str:
    """Таблица PyQt → HTML (простые ячейки)."""
    parts = [
        '<html><head><meta charset="utf-8">',
        "<style>table{border-collapse:collapse;width:100%;}td,th{border:1px solid #444;padding:6px;font-size:11pt;}"
        "th{background:#eee;}</style></head><body>",
    ]
    if title:
        parts.append(f"<h2>{html_module.escape(title)}</h2>")
    parts.append("<table>")
    parts.append("<tr>")
    for c in range(table.columnCount()):
        h = table.horizontalHeaderItem(c)
        parts.append(f"<th>{html_module.escape(h.text() if h else '')}</th>")
    parts.append("</tr>")
    for r in range(table.rowCount()):
        parts.append("<tr>")
        for c in range(table.columnCount()):
            it = table.item(r, c)
            parts.append(f"<td>{html_module.escape(it.text() if it else '')}</td>")
        parts.append("</tr>")
    parts.append("</table></body></html>")
    return "".join(parts)


def plain_text_to_html(title: str, body: str) -> str:
    return (
        '<html><head><meta charset="utf-8"></head><body>'
        f"<h2>{html_module.escape(title)}</h2>"
        f"<pre style='font-family:Segoe UI, sans-serif; white-space:pre-wrap;'>{html_module.escape(body)}</pre>"
        "</body></html>"
    )


def print_html(html_content: str, parent: Optional[QWidget] = None) -> None:
    doc = QTextDocument()
    doc.setHtml(html_content)
    printer = QPrinter(QPrinter.HighResolution)
    dlg = QPrintDialog(printer, parent)
    if dlg.exec_() == QPrintDialog.Accepted:
        doc.print_(printer)


def export_html_to_pdf(
    html_content: str,
    parent: Optional[QWidget] = None,
    default_path: str = "document.pdf",
) -> None:
    path, _ = QFileDialog.getSaveFileName(
        parent, "Сохранить PDF", default_path, "PDF (*.pdf)",
    )
    if not path:
        return
    if not path.lower().endswith(".pdf"):
        path += ".pdf"
    doc = QTextDocument()
    doc.setHtml(html_content)
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    doc.print_(printer)


def export_html_for_word(
    html_content: str,
    parent: Optional[QWidget] = None,
    default_path: str = "document.html",
) -> None:
    """Сохраняет UTF-8 HTML; Word открывает и может «Сохранить как .docx»."""
    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Сохранить для Word (HTML)",
        default_path,
        "HTML (*.html *.htm);;Все файлы (*.*)",
    )
    if not path:
        return
    if not path.lower().endswith((".html", ".htm")):
        path += ".html"
    Path(path).write_text(html_content, encoding="utf-8")


def print_table(table: QTableWidget, title: str, parent: Optional[QWidget] = None) -> None:
    print_html(qtable_widget_to_html(table, title), parent)


def pdf_table(
    table: QTableWidget,
    title: str,
    parent: Optional[QWidget] = None,
    default_name: str = "table.pdf",
) -> None:
    export_html_to_pdf(qtable_widget_to_html(table, title), parent, default_name)
