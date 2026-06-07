"""Экспорт отчётов в Excel (ТЗ)."""
from __future__ import annotations

from io import BytesIO
from typing import Iterable, Sequence

from fastapi.responses import Response


def rows_to_xlsx(
    headers: Sequence[str],
    rows: Iterable[Sequence],
    *,
    filename: str = "export.xlsx",
) -> Response:
    try:
        from openpyxl import Workbook
    except ImportError as e:
        raise RuntimeError(f"openpyxl is not installed: {e}") from e

    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append([_cell(v) for v in row])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _cell(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
