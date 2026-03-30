"""Inspect a single Access file: path, size, table types, row counts where readable."""
import os
import sys
import json

import pyodbc

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Default: archive file
DB_NAME = os.environ.get("ACCDB_NAME", "База данных по наградам - 05-06-2024_архив.accdb")
DB_PATH = os.path.join(PROJECT, DB_NAME)


def main():
    print(f"File: {DB_PATH}")
    print(f"Exists: {os.path.exists(DB_PATH)}")
    if os.path.exists(DB_PATH):
        print(f"Size: {os.path.getsize(DB_PATH):,} bytes")
    print()

    drivers = [d for d in pyodbc.drivers() if "Access" in d]
    if not drivers:
        print("No Access ODBC driver.")
        sys.exit(1)
    conn_str = f"DRIVER={{{drivers[0]}}};DBQ={DB_PATH};"
    print(f"Driver: {drivers[0]}\n")

    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()

    by_type = {}
    for row in cur.tables():
        t = row.table_type
        name = row.table_name
        if name.startswith("~"):
            continue
        by_type.setdefault(t, []).append(name)

    print("=== Objects by type (user objects only, no MSys) ===")
    for t in sorted(by_type.keys()):
        names = [n for n in by_type[t] if not n.startswith("MSys")]
        if not names:
            continue
        print(f"\n{t}: {len(names)}")
        for n in sorted(names)[:80]:
            print(f"  - {n}")
        if len(names) > 80:
            print(f"  ... and {len(names) - 80} more")

    # Try row counts for TABLE and LINKED (SYNONYM)
    print("\n=== Row counts (first 35 tables that are not views) ===")
    candidates = []
    for t in ("TABLE", "SYNONYM"):
        for n in by_type.get(t, []):
            if not n.startswith("MSys"):
                candidates.append(n)
    for name in sorted(candidates)[:35]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM [{name}]")
            cnt = cur.fetchone()[0]
            print(f"  {name}: {cnt} rows")
        except Exception as e:
            print(f"  {name}: ERROR {e}")

    out = {"path": DB_PATH, "size": os.path.getsize(DB_PATH), "types": {k: len(v) for k, v in by_type.items()}}
    outp = os.path.join(os.path.dirname(__file__), "archive_inspect_summary.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nSummary saved: {outp}")
    conn.close()


if __name__ == "__main__":
    main()
