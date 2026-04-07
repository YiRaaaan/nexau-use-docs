---
name: enterprise_product
description: Use this skill when the user asks about an enterprise's products — product names, revenue per product, daily production capacity, or associated intellectual property (patents). One row per enterprise-product pair, joined to enterprise_basic via credit_code.
---

# enterprise_product — 企业产品与知识产权

One row per (enterprise, product) pair. An enterprise can have multiple products distinguished by `product_index`. Each row also lists up to three associated IP / patent names.

## When to use

- "What products does enterprise X make?"
- "Top 10 products by revenue"
- "Which enterprises have more than 3 products?"
- "Sum of product revenue per industry"
- "Find all patents containing the keyword …"

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Internal id |
| `credit_code` | TEXT | Join key to `enterprise_basic` |
| `product_index` | INTEGER | 产品序号 within an enterprise (1, 2, 3, …) |
| `product_name` | TEXT | 产品名称 (sanitized as `产品_N`) |
| `product_revenue` | REAL | 产品营收 (万元) |
| `daily_capacity` | TEXT | 日产能 — numeric stored as TEXT |
| `capacity_unit` | TEXT | 产能单位, one of `件/日`, `吨/日`, `台/日`, `套/日` |
| `ip_name_1` | TEXT | 关联知识产权 1 名称 |
| `ip_name_2` | TEXT | 关联知识产权 2 名称 |
| `ip_name_3` | TEXT | 关联知识产权 3 名称 |
| `created_at`, `updated_at` | TEXT | Timestamps |

## Example queries

**Top 10 products by revenue with their owning enterprise:**

```sql
SELECT b.enterprise_name, p.product_name, p.product_revenue
FROM enterprise_product p
JOIN enterprise_basic b ON b.credit_code = p.credit_code
ORDER BY p.product_revenue DESC
LIMIT 10;
```

**Enterprises with 3 or more products:**

```sql
SELECT b.enterprise_name, COUNT(*) AS n_products
FROM enterprise_product p
JOIN enterprise_basic b ON b.credit_code = p.credit_code
GROUP BY p.credit_code
HAVING n_products >= 3
ORDER BY n_products DESC;
```

**Total product revenue per industry:**

```sql
SELECT b.industry_level1, SUM(p.product_revenue) AS total_revenue
FROM enterprise_product p
JOIN enterprise_basic b ON b.credit_code = p.credit_code
GROUP BY b.industry_level1
ORDER BY total_revenue DESC;
```

## Gotchas

- `daily_capacity` is TEXT — `CAST(daily_capacity AS REAL)` for numeric work.
- Patent names are sanitized; do not assume real-world IP databases.
- An enterprise can have 0 rows here — use a `LEFT JOIN` if you need every enterprise.
