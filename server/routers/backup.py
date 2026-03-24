import csv
import io
import os
import subprocess
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from database import get_db, engine
from config import DATABASE_URL, BACKUP_DIR

router = APIRouter()


def _parse_pg_url(url: str) -> dict:
    """Extract host, port, dbname, user, password from a PostgreSQL URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": parsed.path.lstrip("/"),
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
    }


@router.get("/export")
def export_dump():
    """Создать и скачать дамп PostgreSQL (pg_dump)."""
    params = _parse_pg_url(DATABASE_URL)
    env = os.environ.copy()
    env["PGPASSWORD"] = params["password"]

    try:
        result = subprocess.run(
            [
                "pg_dump",
                "-h", params["host"],
                "-p", params["port"],
                "-U", params["user"],
                "-F", "c",
                params["dbname"],
            ],
            capture_output=True,
            env=env,
            timeout=120,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="pg_dump not found on server")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="pg_dump timed out")

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"pg_dump failed: {result.stderr.decode(errors='replace')}",
        )

    return StreamingResponse(
        io.BytesIO(result.stdout),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=backup.dump"},
    )


@router.post("/import")
def import_dump(file: UploadFile = File(...)):
    """Загрузить и восстановить БД из дампа (pg_restore)."""
    params = _parse_pg_url(DATABASE_URL)
    env = os.environ.copy()
    env["PGPASSWORD"] = params["password"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".dump") as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "pg_restore",
                "-h", params["host"],
                "-p", params["port"],
                "-U", params["user"],
                "-d", params["dbname"],
                "--clean",
                "--if-exists",
                tmp_path,
            ],
            capture_output=True,
            env=env,
            timeout=300,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="pg_restore not found on server")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="pg_restore timed out")
    finally:
        os.unlink(tmp_path)

    if result.returncode != 0:
        stderr_text = result.stderr.decode(errors="replace")
        if "ERROR" in stderr_text:
            raise HTTPException(
                status_code=500,
                detail=f"pg_restore errors: {stderr_text}",
            )

    return {"status": "ok", "detail": "Database restored successfully"}


@router.get("/export/csv/{table_name}")
def export_csv(table_name: str, db: Session = Depends(get_db)):
    """Экспортировать указанную таблицу в CSV."""
    inspector = inspect(engine)
    available_tables = inspector.get_table_names()
    if table_name not in available_tables:
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table_name}' not found. Available: {available_tables}",
        )

    rows = db.execute(text(f'SELECT * FROM "{table_name}"'))
    columns = list(rows.keys())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(row)
    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={table_name}.csv",
        },
    )
