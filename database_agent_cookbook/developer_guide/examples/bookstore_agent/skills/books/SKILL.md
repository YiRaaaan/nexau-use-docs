---
name: books
description: >-
  Use this skill whenever the user asks about books — titles, authors, genres,
  prices, stock, or publishers. This table contains the full book catalog.
  Join to orders via book_id.
---

# books — 书籍目录

The complete book catalog. One row per book, keyed by `id`.

## When to use

- "What science fiction books do we have?"
- "Which book is the most expensive?"
- "How many books by 刘慈欣?"
- "List all technical books published after 2015"

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Book ID — join key for `orders.book_id` |
| `title` | TEXT | 书名 |
| `author` | TEXT | 作者 |
| `genre` | TEXT | 分类: `文学` / `技术` / `历史` / `科幻` / `经管` |
| `price` | TEXT | 价格（元）— **TEXT not numeric**, use `CAST(price AS REAL)` for comparisons |
| `stock` | INTEGER | 库存数量 |
| `publisher` | TEXT | 出版社 |
| `publish_year` | INTEGER | 出版年份 |

## Common values

- `genre`: `文学`, `技术`, `历史`, `科幻`, `经管`
- `publisher` examples: `人民邮电出版社`, `中信出版社`, `重庆出版社`

## Example queries

**Most expensive books:**

```sql
SELECT title, author, CAST(price AS REAL) AS price_yuan
FROM books
ORDER BY price_yuan DESC
LIMIT 5;
```

**Books by genre:**

```sql
SELECT genre, COUNT(*) AS n, AVG(CAST(price AS REAL)) AS avg_price
FROM books
GROUP BY genre
ORDER BY n DESC;
```

**Search by author:**

```sql
SELECT title, genre, price, publish_year
FROM books
WHERE author = '刘慈欣';
```

## Gotchas

- `price` is **TEXT**, not REAL — always `CAST(price AS REAL)` for numeric operations.
- `genre` uses Chinese category names. For fuzzy search use `LIKE '%技术%'`.
- `publish_year` is INTEGER and can be used directly in comparisons.
