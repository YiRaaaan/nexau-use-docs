---
name: orders
description: >-
  Use this skill whenever the user asks about orders, purchases, sales, or
  transaction history. Join to customers via customer_id and to books via
  book_id.
---

# orders — 订单记录

All purchase orders. Each row represents one line item (one book per order row).

## When to use

- "How many orders were placed in March?"
- "What's the total revenue?"
- "Which customer has the most orders?"
- "Show me all pending orders"

**This table is for transactional data.** For customer details, use `customers`.
For book details, use `books`.

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Order ID |
| `customer_id` | INTEGER FK | → `customers.id` |
| `book_id` | INTEGER FK | → `books.id` |
| `quantity` | INTEGER | 购买数量 |
| `total_price` | TEXT | 订单总价（元）— **TEXT**, use `CAST(total_price AS REAL)` |
| `order_date` | TEXT | 下单日期 (ISO date, e.g. `2025-01-15`) |
| `status` | TEXT | 订单状态: `已完成` / `待发货` / `已取消` |

## Common values

- `status`: `已完成`, `待发货`, `已取消`

## Example queries

**Monthly revenue:**

```sql
SELECT strftime('%Y-%m', order_date) AS month,
       SUM(CAST(total_price AS REAL)) AS revenue
FROM orders
WHERE status != '已取消'
GROUP BY month
ORDER BY month;
```

**Top customers by number of orders:**

```sql
SELECT c.name, COUNT(*) AS order_count,
       SUM(CAST(o.total_price AS REAL)) AS total_spent
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status != '已取消'
GROUP BY c.id
ORDER BY total_spent DESC
LIMIT 5;
```

**Join with books to see what was ordered:**

```sql
SELECT c.name AS customer, b.title AS book, o.quantity,
       o.total_price, o.order_date, o.status
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN books b ON o.book_id = b.id
ORDER BY o.order_date DESC
LIMIT 10;
```

## Gotchas

- `total_price` is **TEXT** — always `CAST(total_price AS REAL)` for numeric operations.
- `order_date` is a TEXT date string in `YYYY-MM-DD` format. Use `date()` or
  `strftime()` for date arithmetic and grouping.
- A row with `status = '已取消'` should usually be **excluded** from revenue
  calculations and most aggregate queries.
- `total_price` is pre-computed (quantity × unit price). Don't re-multiply
  `quantity * books.price` — it may differ due to discounts.
