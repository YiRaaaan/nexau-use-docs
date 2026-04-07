# /// script
# requires-python = ">=3.11"
# ///
"""Scrub source-PG row IDs from enterprise.sqlite and fix the broken
industry_enterprise FK.

Operations (all wrapped in a single transaction):

1. enterprise_contact.id  → 1..N (sequential, by current id ASC)
2. enterprise_product.id  → 1..N
3. industry.id            → 1..N, with parent_id and path[] remapped
4. chain_id=45            → 1 in industry and industry_enterprise
5. industry_enterprise    → drop and regenerate 37 rows with valid
                            (industry_id, credit_code) pairs, plus the
                            corresponding industry_path leading to that node.
"""

from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "enterprise.sqlite"
SEED = 20260407
NEW_CHAIN_ID = 1
IE_ROW_COUNT = 37


def renumber(conn: sqlite3.Connection, table: str) -> dict[int, int]:
    cur = conn.execute(f'SELECT id FROM "{table}" ORDER BY id')
    old_ids = [r[0] for r in cur.fetchall()]
    remap = {old: new for new, old in enumerate(old_ids, start=1)}
    # Update via a temporary offset to avoid collisions during the rewrite.
    offset = max(old_ids) + 1_000_000
    conn.execute(f'UPDATE "{table}" SET id = id + ?', (offset,))
    for old, new in remap.items():
        conn.execute(f'UPDATE "{table}" SET id = ? WHERE id = ?', (new, old + offset))
    return remap


def scrub_industry(conn: sqlite3.Connection) -> dict[int, int]:
    """Renumber industry.id and rewrite parent_id + path JSON arrays."""
    rows = conn.execute(
        "SELECT id, parent_id, path FROM industry ORDER BY id"
    ).fetchall()
    old_ids = [r[0] for r in rows]
    remap = {old: new for new, old in enumerate(old_ids, start=1)}

    offset = max(old_ids) + 1_000_000
    conn.execute("UPDATE industry SET id = id + ?", (offset,))

    for old_id, parent_id, path_json in rows:
        new_id = remap[old_id]
        new_parent = remap.get(parent_id) if parent_id is not None else None
        old_path = json.loads(path_json) if path_json else []
        new_path = [remap[p] for p in old_path if p in remap]
        conn.execute(
            "UPDATE industry SET id = ?, parent_id = ?, path = ?, chain_id = ? "
            "WHERE id = ?",
            (new_id, new_parent, json.dumps(new_path), NEW_CHAIN_ID, old_id + offset),
        )
    return remap


def rebuild_industry_enterprise(conn: sqlite3.Connection) -> None:
    """The original industry_enterprise.industry_id values point at industry
    rows that were never sampled into the mock (0/37 overlap with industry.id).
    Drop them and synthesize valid pairs.
    """
    rng = random.Random(SEED)

    industry_rows = conn.execute(
        "SELECT id, parent_id FROM industry"
    ).fetchall()
    industry_by_id = {r[0]: r[1] for r in industry_rows}
    leaf_ids = [
        i for i in industry_by_id
        if not any(p == i for p in industry_by_id.values())
    ] or list(industry_by_id.keys())

    credit_codes = [
        r[0] for r in conn.execute("SELECT credit_code FROM enterprise_basic")
    ]

    def path_to(node: int) -> list[int]:
        chain: list[int] = []
        cur: int | None = node
        while cur is not None:
            chain.append(cur)
            cur = industry_by_id.get(cur)
        return list(reversed(chain))

    conn.execute("DELETE FROM industry_enterprise")

    seen: set[tuple[int, str]] = set()
    created_at = "2025-12-31T14:02:19.139869+08:00"
    inserted = 0
    while inserted < IE_ROW_COUNT:
        node = rng.choice(leaf_ids)
        cc = rng.choice(credit_codes)
        if (node, cc) in seen:
            continue
        seen.add((node, cc))
        conn.execute(
            "INSERT INTO industry_enterprise "
            "(industry_id, credit_code, created_at, chain_id, industry_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (node, cc, created_at, NEW_CHAIN_ID, json.dumps(path_to(node))),
        )
        inserted += 1


def main() -> None:
    assert DB.exists(), DB
    conn = sqlite3.connect(DB)
    try:
        conn.execute("BEGIN")

        contact_remap = renumber(conn, "enterprise_contact")
        product_remap = renumber(conn, "enterprise_product")
        industry_remap = scrub_industry(conn)
        rebuild_industry_enterprise(conn)

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    print(
        f"Renumbered enterprise_contact: {len(contact_remap)} rows, "
        f"enterprise_product: {len(product_remap)} rows, "
        f"industry: {len(industry_remap)} rows. "
        f"Rebuilt industry_enterprise with {IE_ROW_COUNT} valid links."
    )


if __name__ == "__main__":
    main()
