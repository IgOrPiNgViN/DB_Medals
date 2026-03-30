"""Чтение зеркала таблиц Access (импорт из CSV)."""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.access_mirror import AccessMirrorRow

router = APIRouter()


@router.get("/tables")
def list_tables(db: Session = Depends(get_db)) -> List[dict]:
    q = (
        db.query(AccessMirrorRow.table_name, func.count(AccessMirrorRow.id))
        .group_by(AccessMirrorRow.table_name)
        .order_by(AccessMirrorRow.table_name)
        .all()
    )
    return [{"name": name, "row_count": cnt} for name, cnt in q]


@router.get("/data")
def get_table_data(
    table: str = Query(..., min_length=1, description="Имя таблицы как в CSV (без .csv)"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        db.query(AccessMirrorRow)
        .filter(AccessMirrorRow.table_name == table)
        .order_by(AccessMirrorRow.row_index)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Таблица «{table}» не найдена или пуста")

    columns: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r.data:
            if k not in seen:
                seen.add(k)
                columns.append(k)

    out_rows = [dict(r.data) for r in rows]
    return {"table": table, "columns": columns, "rows": out_rows}
