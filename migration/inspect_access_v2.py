"""Extract table/view names and query SQL from Access front-end."""
import pyodbc
import json
import os
import sys

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "База данных по наградам - 05-06-2024.accdb",
)


def get_connection():
    drivers = [d for d in pyodbc.drivers() if "Access" in d]
    if not drivers:
        sys.exit("No Access driver found")
    conn_str = f"DRIVER={{{drivers[0]}}};DBQ={DB_PATH};"
    return pyodbc.connect(conn_str)


def main():
    conn = get_connection()
    cursor = conn.cursor()

    objects_by_type = {}
    for row in cursor.tables():
        ttype = row.table_type
        name = row.table_name
        if name.startswith("~"):
            continue
        objects_by_type.setdefault(ttype, []).append(name)

    result = {"tables_by_type": {}, "query_sql": {}, "linked_table_columns": {}}

    for ttype, names in sorted(objects_by_type.items()):
        result["tables_by_type"][ttype] = sorted(names)

    # Try to read query SQL from MSysQueries
    try:
        cursor.execute("""
            SELECT DISTINCT Name1 
            FROM MSysQueries 
            WHERE Name1 IS NOT NULL 
            ORDER BY Name1
        """)
        query_names = [r[0] for r in cursor.fetchall()]
        
        for qname in query_names:
            try:
                cursor.execute(
                    "SELECT Attribute, Expression, Name1, Name2, Flag "
                    "FROM MSysQueries WHERE Name1 = ? ORDER BY Attribute",
                    [qname]
                )
                rows = []
                for r in cursor.fetchall():
                    rows.append({
                        "Attribute": r[0],
                        "Expression": r[1],
                        "Name1": r[2],
                        "Name2": r[3],
                        "Flag": r[4],
                    })
                result["query_sql"][qname] = rows
            except Exception as e:
                result["query_sql"][qname] = f"ERROR: {e}"
    except Exception as e:
        result["query_sql"]["_error"] = str(e)

    # Try to read linked table info from MSysObjects
    try:
        cursor.execute("""
            SELECT Name, ForeignName, Database 
            FROM MSysObjects 
            WHERE Type = 6 
            ORDER BY Name
        """)
        for r in cursor.fetchall():
            result["linked_table_columns"][r[0]] = {
                "foreign_name": r[1],
                "database": r[2],
            }
    except Exception as e:
        result["linked_table_columns"]["_error"] = str(e)

    # Try to get column metadata for linked tables (SYNONYM)
    synonyms = objects_by_type.get("SYNONYM", [])
    for tbl in synonyms:
        if tbl.startswith("MSys"):
            continue
        cols = []
        try:
            for row in cursor.columns(table=tbl):
                cols.append({
                    "name": row.column_name,
                    "type": row.type_name,
                    "size": row.column_size,
                    "nullable": row.nullable,
                })
        except Exception:
            pass
        if cols:
            if tbl in result["linked_table_columns"]:
                result["linked_table_columns"][tbl]["columns"] = cols
            else:
                result["linked_table_columns"][tbl] = {"columns": cols}

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "access_detailed.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    # Print summary
    print("=== OBJECTS BY TYPE ===")
    for ttype, names in sorted(objects_by_type.items()):
        non_sys = [n for n in names if not n.startswith("MSys")]
        print(f"\n{ttype} ({len(non_sys)} user objects):")
        for n in sorted(non_sys):
            print(f"  - {n}")

    print(f"\n\n=== LINKED TABLES WITH COLUMNS ===")
    for tbl in synonyms:
        if tbl.startswith("MSys"):
            continue
        info = result["linked_table_columns"].get(tbl, {})
        cols = info.get("columns", [])
        print(f"\n  {tbl}:")
        if cols:
            for c in cols:
                print(f"    {c['name']:40s} {c['type']:15s} size={c['size']}")
        else:
            print(f"    (no column metadata available)")

    print(f"\nSaved detailed info to: {out_path}")
    conn.close()


if __name__ == "__main__":
    main()
