---
name: industry
description: Use this skill when the user asks about industry chains, the position of an industry node (上游/中游/下游), parent-child relationships between industries, or wants to traverse an industry tree. Pair with `industry_enterprise` to map enterprises onto chain nodes.
---

# industry — 行业链节点

A hierarchical reference table describing industry chains. Each row is one node in a chain (e.g. "AI 上游 — 算力 — GPU 集群"), and the tree is encoded both via `parent_id` and via a materialized `path` column. The chain a node belongs to is identified by `chain_id`.

To find which enterprises belong to a node, join `industry_enterprise` on `industry_id`.

## When to use

- "What does the AI industry chain look like?" → traverse `industry` filtered by `chain_id`
- "Which node in the chain is X?" → look up by `name`
- "List all leaf nodes (downstream applications) of the AI chain" → filter on `depth` and `chain_position`
- "Which enterprises belong to the GPU cluster node?" → join `industry_enterprise`
- For per-enterprise industry classification at the row level, prefer `enterprise_basic.industry_level1..4` (it is denormalized and faster).

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Internal node id — referenced by `industry_enterprise.industry_id` |
| `chain_id` | INTEGER | Identifier of the industry chain this node belongs to (e.g. `45` = AI chain) |
| `parent_id` | INTEGER | Parent node id within the same chain. NULL for root nodes. |
| `name` | TEXT | Human-readable node name (e.g. `上游（基础要素与基础设施）`) |
| `description` | TEXT | Long natural-language description of what the node represents |
| `path` | TEXT | Materialized ancestor path as a JSON array of ids (e.g. `[3821, 3836, 3837]`). Useful for fast subtree queries with `LIKE`. |
| `depth` | INTEGER | Tree depth, 0 = root |
| `sort_order` | INTEGER | Display ordering among siblings |
| `chain_position` | TEXT | One of `up` (上游), `mid` (中游), `down` (下游) — only set on top-level nodes |
| `icon` | TEXT | UI icon hint (e.g. `arrow-up-from-line`) |
| `created_at`, `updated_at` | TEXT | ISO timestamps |

## Common values

- `depth`: `0` (chain root, ~2 rows), `1` (上/中/下游, ~6 rows), `2` (sub-categories, the bulk of the table)
- `chain_position`: `up`, `mid`, `down` (only on depth-1 nodes)

## Example queries

**Show the top-level structure of every chain:**

```sql
SELECT chain_id, depth, name, chain_position
FROM industry
WHERE depth <= 1
ORDER BY chain_id, depth, sort_order;
```

**All leaf nodes under a specific chain (chain_id = 45 is the AI chain):**

```sql
SELECT id, name, depth, path
FROM industry
WHERE chain_id = 45
  AND id NOT IN (SELECT DISTINCT parent_id FROM industry WHERE parent_id IS NOT NULL)
ORDER BY depth, sort_order;
```

**Find enterprises mapped to any "上游" node of the AI chain:**

```sql
SELECT b.enterprise_name, i.name AS industry_node
FROM industry i
JOIN industry_enterprise ie ON ie.industry_id = i.id
JOIN enterprise_basic b     ON b.credit_code = ie.credit_code
WHERE i.chain_id = 45
  AND i.chain_position = 'up';
```

**Walk up from a node to its root using `path`:**

```sql
SELECT id, depth, name
FROM industry
WHERE id IN (3821, 3836, 3837)   -- ids from the child node's `path` column
ORDER BY depth;
```

## Gotchas

- `path` is a JSON array stored as TEXT. SQLite has `json_each()` if you need to expand it, but for simple subtree filtering `LIKE '%, 3836,%'` is usually enough.
- `chain_position` is only populated on depth-1 nodes. Don't filter on it for leaf queries.
- `parent_id` is NULL on roots — use `IS NULL`, not `= 0`.
