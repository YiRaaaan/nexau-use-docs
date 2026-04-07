---
name: industry_enterprise
description: Use this skill when the user wants to map enterprises to industry-chain nodes — i.e. "which enterprises belong to chain node X" or "which chain nodes does enterprise X participate in". This is the join table between `enterprise_basic` and `industry`.
---

# industry_enterprise — 企业 ↔ 行业链节点 映射

A many-to-many join table linking enterprises (`enterprise_basic.credit_code`) to industry-chain nodes (`industry.id`). One enterprise can map to multiple chain nodes; one node typically has many enterprises.

For per-enterprise denormalized industry classification (the four `industry_level1..4` columns), use `enterprise_basic` directly — it's faster and doesn't require a join. Use this table when you need the **chain-graph view** (上游/中游/下游 of a specific chain).

## When to use

- "Which enterprises belong to the AI chain (chain_id 45)?"
- "How many enterprises are in each upstream node of the AI chain?"
- "Which chain nodes does enterprise X participate in?"
- "Which enterprises are upstream AND downstream simultaneously?"

## Schema

| Column | Type | Description |
|---|---|---|
| `industry_id` | INTEGER PK | FK to `industry.id` |
| `credit_code` | TEXT PK | FK to `enterprise_basic.credit_code` |
| `chain_id` | INTEGER | Denormalized chain id (matches `industry.chain_id`) |
| `industry_path` | TEXT | JSON array of ancestor node ids — copied from `industry.path` for fast filtering |
| `created_at` | TEXT | Timestamp |

The composite primary key is `(industry_id, credit_code)`.

## Example queries

**All enterprises in chain 45 with their node names:**

```sql
SELECT b.enterprise_name, i.name AS chain_node, i.chain_position
FROM industry_enterprise ie
JOIN industry i         ON i.id = ie.industry_id
JOIN enterprise_basic b ON b.credit_code = ie.credit_code
WHERE ie.chain_id = 45
ORDER BY i.depth, i.sort_order;
```

**Enterprise count per node within the AI chain:**

```sql
SELECT i.name, COUNT(*) AS n_enterprises
FROM industry_enterprise ie
JOIN industry i ON i.id = ie.industry_id
WHERE ie.chain_id = 45
GROUP BY ie.industry_id
ORDER BY n_enterprises DESC;
```

**Which chain nodes does a specific enterprise belong to:**

```sql
SELECT i.chain_id, i.name, i.chain_position, i.depth
FROM industry_enterprise ie
JOIN industry i ON i.id = ie.industry_id
WHERE ie.credit_code = 'MOCKCREDIT0000000034';
```

## Gotchas

- `industry_path` is a JSON array stored as TEXT (e.g. `[3821, 3836, 3837]`). Use `LIKE '%, 3836,%'` for fast subtree filtering.
- `chain_id` is denormalized — it's identical to the value you'd get by joining `industry`. Use it directly to skip the join when you only need to filter by chain.
- An enterprise may have no rows here at all — `LEFT JOIN` if you need every enterprise.
