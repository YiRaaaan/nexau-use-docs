---
name: customers
description: >-
  Use this skill whenever the user asks about customer information — names,
  emails, cities, or membership levels. This is the primary table for customer
  identity. Join to orders via customer_id.
---

# customers — 客户信息

The customer registry for the bookstore. One row per customer, keyed by `id`.

## When to use

- "How many customers are in 北京?"
- "List all 金卡 members"
- "Who is customer zhangsan@example.com?"
- "Which cities do our customers come from?"

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Customer ID — join key for `orders.customer_id` |
| `name` | TEXT | 客户姓名 |
| `email` | TEXT UNIQUE | 邮箱 |
| `city` | TEXT | 所在城市 (e.g. `北京`, `上海`, `广州`) |
| `member_level` | TEXT | 会员等级: `普通` / `银卡` / `金卡` / `钻石` |
| `created_at` | TEXT | 注册时间 (ISO datetime) |

## Common values

- `city`: `北京`, `上海`, `广州`, `深圳`, `杭州`, `成都`
- `member_level`: `普通`, `银卡`, `金卡`, `钻石`

## Example queries

**Count customers by city:**

```sql
SELECT city, COUNT(*) AS n
FROM customers
GROUP BY city
ORDER BY n DESC;
```

**List all 金卡 or above members:**

```sql
SELECT name, email, city, member_level
FROM customers
WHERE member_level IN ('金卡', '钻石')
ORDER BY name;
```

## Gotchas

- `member_level` has a hierarchy: `普通` < `银卡` < `金卡` < `钻石`. There's no
  numeric rank column — use `CASE WHEN` to impose ordering if needed.
- `created_at` uses ISO datetime format. Use `date()` or `strftime()` for date arithmetic.
