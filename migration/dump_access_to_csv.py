"""
Выгрузка всех пользовательских таблиц из Access в CSV (UTF-8 с BOM для Excel).

Когда использовать:
  - есть файл back-end .accdb с таблицами (или полная база без битых связей);
  - путь к нему доступен с этого компьютера.

Не сработает, если таблицы — только связи на недоступный Z:\\... (как сейчас у фронта).

Запуск (PowerShell):
  cd "путь\\к\\проекту"
  $env:ACCDB_PATH = "C:\\полный\\путь\\к\\файлу_с_данными.accdb"
  $env:OUT_DIR = "migration\\csv_export"
  python migration\\dump_access_to_csv.py

Без ACCDB_PATH — берётся файл _архив из папки проекта (может снова дать ошибки на связанных таблицах).
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

try:
    import pyodbc
except ImportError:
    print("Установите: pip install pyodbc")
    sys.exit(1)

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT / "База данных по наградам - 05-06-2024_архив.accdb"


def get_connection(db_path: str):
    drivers = [d for d in pyodbc.drivers() if "Access" in d]
    if not drivers:
        raise RuntimeError("Нет драйвера Microsoft Access ODBC")
    return pyodbc.connect(f"DRIVER={{{drivers[0]}}};DBQ={db_path};")


def list_table_names(conn) -> list[str]:
    cur = conn.cursor()
    names: list[str] = []
    for row in cur.tables(tableType="TABLE"):
        n = row.table_name
        if n.startswith("MSys") or n.startswith("~"):
            continue
        names.append(n)
    for row in cur.tables(tableType="SYNONYM"):
        n = row.table_name
        if n.startswith("MSys") or n.startswith("~"):
            continue
        if n not in names:
            names.append(n)
    return sorted(names)


def dump_table(conn, table: str, out_path: Path) -> tuple[bool, str]:
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM [{table}]")
    except Exception as e:
        return False, str(e)
    rows = cur.fetchall()
    if cur.description is None:
        return True, "0 rows"
    colnames = [d[0] for d in cur.description]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        w.writerow(colnames)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
    return True, f"{len(rows)} rows"


def main():
    db_path = os.environ.get("ACCDB_PATH", str(DEFAULT_DB))
    out_root = Path(os.environ.get("OUT_DIR", str(PROJECT / "migration" / "csv_export")))

    print(f"Файл: {db_path}")
    print(f"Папка выгрузки: {out_root}")
    if not os.path.isfile(db_path):
        print("ОШИБКА: файл не найден.")
        sys.exit(1)

    conn = get_connection(db_path)
    tables = list_table_names(conn)
    print(f"Найдено таблиц (TABLE+SYNONYM): {len(tables)}\n")

    ok_n = 0
    err_n = 0
    for t in tables:
        safe_name = (
            t.replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace("?", "_")
        )
        out_file = out_root / f"{safe_name}.csv"
        ok, msg = dump_table(conn, t, out_file)
        if ok:
            print(f"  OK  {t} -> {out_file.name} ({msg})")
            ok_n += 1
        else:
            print(f"  ERR {t}: {msg}")
            err_n += 1

    conn.close()
    print(f"\nГотово: успешно {ok_n}, ошибок {err_n}")
    if err_n:
        print(
            "\nОшибки на связанных таблицах — нет доступа к back-end (часто путь Z:\\...).\n"
            "Нужен файл .accdb с данными на этом ПК или запрос к организации."
        )


if __name__ == "__main__":
    main()
