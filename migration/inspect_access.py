"""Inspect Access database structure: tables, columns, types, relationships."""
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
        print("ERROR: No Microsoft Access ODBC driver found.")
        print("Available drivers:", pyodbc.drivers())
        sys.exit(1)
    driver = drivers[0]
    print(f"Using driver: {driver}")
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"DBQ={DB_PATH};"
    )
    return pyodbc.connect(conn_str)


def inspect_all_objects(conn):
    """List all objects of all types via cursor.tables()."""
    cursor = conn.cursor()
    results = {}
    for row in cursor.tables():
        ttype = row.table_type
        name = row.table_name
        if ttype not in results:
            results[ttype] = []
        results[ttype].append(name)
    return results


def inspect_columns(conn, table_name):
    cursor = conn.cursor()
    columns = []
    for row in cursor.columns(table=table_name):
        columns.append({
            "name": row.column_name,
            "type": row.type_name,
            "size": row.column_size,
            "nullable": row.nullable,
        })
    return columns


def inspect_primary_keys(conn, table_name):
    cursor = conn.cursor()
    pks = []
    try:
        for row in cursor.primaryKeys(table=table_name):
            pks.append(row.column_name)
    except Exception:
        pass
    return pks


def inspect_foreign_keys(conn, table_name):
    cursor = conn.cursor()
    fks = []
    try:
        for row in cursor.foreignKeys(table=table_name):
            fks.append({
                "column": row.fkcolumn_name,
                "ref_table": row.pktable_name,
                "ref_column": row.pkcolumn_name,
            })
    except Exception:
        pass
    return fks


def count_rows(conn, table_name):
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        return cursor.fetchone()[0]
    except Exception as e:
        return f"ERROR: {e}"


def sample_rows(conn, table_name, limit=3):
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT TOP {limit} * FROM [{table_name}]")
        cols = [desc[0] for desc in cursor.description]
        rows = []
        for row in cursor.fetchall():
            rows.append({cols[i]: repr(row[i]) for i in range(len(cols))})
        return rows
    except Exception as e:
        return f"ERROR: {e}"


def main():
    print(f"Database: {DB_PATH}")
    print(f"Exists: {os.path.exists(DB_PATH)}")
    print()

    conn = get_connection()

    print("=== ALL DATABASE OBJECTS ===")
    all_objects = inspect_all_objects(conn)
    for obj_type, names in sorted(all_objects.items()):
        filtered = [n for n in names if not n.startswith("~")]
        print(f"\n  Type: '{obj_type}' ({len(filtered)} objects)")
        for name in sorted(filtered):
            print(f"    - {name}")

    user_tables = []
    for ttype in ["TABLE", "LINK", "SYSTEM TABLE", "ACCESS TABLE", ""]:
        if ttype in all_objects:
            for name in all_objects[ttype]:
                if not name.startswith("MSys") and not name.startswith("~"):
                    user_tables.append(name)

    if not user_tables:
        for ttype, names in all_objects.items():
            for name in names:
                if not name.startswith("MSys") and not name.startswith("~"):
                    if name not in user_tables:
                        user_tables.append(name)

    user_tables = sorted(set(user_tables))
    print(f"\n\n=== USER TABLES ({len(user_tables)}) ===\n")

    schema = {}
    for tbl in user_tables:
        cols = inspect_columns(conn, tbl)
        pks = inspect_primary_keys(conn, tbl)
        fks = inspect_foreign_keys(conn, tbl)
        rows = count_rows(conn, tbl)
        sample = sample_rows(conn, tbl, 2)

        schema[tbl] = {
            "columns": cols,
            "primary_keys": pks,
            "foreign_keys": fks,
            "row_count": rows,
            "sample": sample,
        }

        print(f"=== {tbl} ({rows} rows) ===")
        print(f"  PK: {pks}")
        for c in cols:
            nullable = "NULL" if c["nullable"] else "NOT NULL"
            pk_mark = " [PK]" if c["name"] in pks else ""
            print(f"  {c['name']:40s} {c['type']:15s} size={c['size']:<6} {nullable}{pk_mark}")
        if fks:
            print(f"  Foreign keys:")
            for fk in fks:
                print(f"    {fk['column']} -> {fk['ref_table']}.{fk['ref_column']}")
        if isinstance(sample, list) and sample:
            print(f"  Sample data:")
            for s in sample:
                for k, v in s.items():
                    vstr = str(v)[:80]
                    print(f"    {k}: {vstr}")
                print("    ---")
        print()

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "access_schema.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSchema saved to: {out_path}")

    conn.close()


if __name__ == "__main__":
    main()
