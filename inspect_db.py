# /// script
# requires-python = ">=3.10"
# dependencies = ["psycopg[binary]", "PySocks"]
# ///
"""Inspect the remote Postgres DB through a SOCKS5 proxy and dump schema."""
import socket
import socks
import json

# Route all sockets through local SOCKS5 proxy
socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 53162)
socket.socket = socks.socksocket

import psycopg

CONN = dict(
    host="14.103.94.133",
    port=5432,
    dbname="north_nova_ei_prod",
    user="nova_ei_readonly",
    password="Twmzoo3YHA&f&EYm",
    connect_timeout=30,
)

def main():
    with psycopg.connect(**CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            print("VERSION:", cur.fetchone()[0])

            cur.execute("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast')
                  AND schema_name NOT LIKE 'pg_temp%'
                  AND schema_name NOT LIKE 'pg_toast%'
                ORDER BY schema_name;
            """)
            schemas = [r[0] for r in cur.fetchall()]
            print("SCHEMAS:", schemas)

            cur.execute("""
                SELECT table_schema, table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = ANY(%s)
                ORDER BY table_schema, table_name;
            """, (schemas,))
            tables = cur.fetchall()
            print(f"TABLES ({len(tables)}):")
            for s, t, ty in tables:
                print(f"  {s}.{t} ({ty})")

            # Columns for every table
            cur.execute("""
                SELECT table_schema, table_name, column_name, data_type,
                       is_nullable, character_maximum_length, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = ANY(%s)
                ORDER BY table_schema, table_name, ordinal_position;
            """, (schemas,))
            cols = cur.fetchall()

            schema_dump = {}
            for s, t, c, dt, nn, clen, np, ns in cols:
                schema_dump.setdefault(f"{s}.{t}", []).append({
                    "name": c, "type": dt, "nullable": nn,
                    "char_len": clen, "num_precision": np, "num_scale": ns,
                })

            with open("schema_dump.json", "w") as f:
                json.dump(schema_dump, f, indent=2, default=str)
            print(f"WROTE schema_dump.json ({len(schema_dump)} tables)")

            # Row counts (best-effort)
            counts = {}
            for s, t, ty in tables:
                if ty != "BASE TABLE":
                    continue
                try:
                    cur.execute(f'SELECT COUNT(*) FROM "{s}"."{t}"')
                    counts[f"{s}.{t}"] = cur.fetchone()[0]
                except Exception as e:
                    counts[f"{s}.{t}"] = f"ERR: {e}"
                    conn.rollback()
            with open("row_counts.json", "w") as f:
                json.dump(counts, f, indent=2, default=str)
            print("WROTE row_counts.json")

if __name__ == "__main__":
    main()
