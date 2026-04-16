# 第 2 章 · 编写 Skill：让 Agent 掌握领域知识

> **本章是整个开发者指南的核心。** Skill 写得好不好，直接决定 Agent 能不能正确回答用户的问题。
>
> 读完本章，你将能够：为任意数据库表编写高质量的 SKILL.md，避免常见陷阱，并理解 Skill 的路由机制。

---

## A. Skill 是什么

Skill 是 NexAU 让模型"学习领域知识"的标准机制。它就是一个**文件夹** + 一个 **`SKILL.md`**：

```
skills/
└── books/
    └── SKILL.md
```

`SKILL.md` 由两部分组成：

```markdown
---
name: books
description: Use this skill whenever the user asks about books — titles,
  authors, genres, prices, stock, or publishers.
---

# books — 书籍目录

正文：表的 schema、常用值、示例 SQL、注意事项...
```

### 两部分各自的角色

| 部分 | 谁在读 | 何时读 | 作用 |
|---|---|---|---|
| **frontmatter**（`name` + `description`） | LLM | **始终可见**——Agent 启动时即加入 context | 路由提示：模型据此决定"当前问题是否需要读取这个 Skill" |
| **正文**（Markdown body） | LLM | **按需加载**——仅当模型决定读取时才注入 | 真正的领域知识：schema、SQL 示例、注意事项 |

这意味着：

- `description` 是**路由标签**——写得精准，模型才能把用户的问题"派发"到正确的 Skill
- 正文是**参考手册**——写得完整，模型才能编写正确的 SQL

> **按需加载的好处**：7 张表的完整 schema 全部塞进 system prompt 会浪费大量 token。Skill 机制让模型只在需要时才读取相关表的知识，既省 token 又减少干扰。

---

## B. SKILL.md 各章节详解

一个完整的数据库 Skill 通常包含以下章节：

### 1. frontmatter: `name` 和 `description`

```yaml
---
name: orders
description: >-
  Use this skill whenever the user asks about orders, purchases, sales, or
  transaction history. Join to customers via customer_id and to books via
  book_id.
---
```

- `name`：Skill 的唯一标识，通常与表名一致
- `description`：**最关键的字段**——模型根据它判断"是否需要读取这个 Skill"。详见下方 [C 节](#c-description-写法深度)

### 2. When to use

列出 3-5 个典型用户问题，帮助模型理解该 Skill 的适用场景：

```markdown
## When to use

- "How many orders were placed in March?"
- "What's the total revenue?"
- "Which customer has the most orders?"
- "Show me all pending orders"
```

这些问题同时也是你验证 Skill 的测试用例——写完 Skill 后，用这些问题测试 Agent 是否能正确回答。

### 3. Schema

用表格列出列名、类型、描述，**标注关键信息**（PK、FK、类型陷阱）：

```markdown
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
```

**关键原则**：类型陷阱紧邻列名标注。`total_price` 是 TEXT 而非 REAL 这件事，是该表最容易踩坑之处——必须在 Schema 表中就标出来，而非等到 Gotchas 章节才提。

### 4. Common values

列出枚举值速查表，减少模型猜测：

```markdown
## Common values

- `status`: `已完成`, `待发货`, `已取消`
- `genre`: `文学`, `技术`, `历史`, `科幻`, `经管`
```

### 5. Example queries

提供 2-3 个**完整、正确**的 SQL 示例。这些示例就是 few-shot（向模型提供几个范例，使其照此编写）——模型读取 Skill 不仅为了"知道有这一列"，更为了"看到正确的 SQL 应当如何编写"：

```markdown
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
```

**示例要求**：
- 必须是可直接运行的完整 SQL，不是伪代码
- 涵盖该表最常见的查询模式（聚合、排序、join）
- 展示正确的类型处理方式（如 `CAST`）

### 6. Gotchas

**最有价值的章节**——列出模型最容易犯的错：

```markdown
## Gotchas

- `total_price` is **TEXT** — always `CAST(total_price AS REAL)` for numeric operations.
- A row with `status = '已取消'` should usually be **excluded** from revenue calculations.
- `total_price` is pre-computed (quantity × unit price). Don't re-multiply
  `quantity * books.price` — it may differ due to discounts.
```

Gotchas 是你的领域经验的结晶。你对数据库越熟悉，写出来的 Gotchas 越有价值。

---

## C. description 写法深度

`description` 是整个 SKILL.md 中**投入产出比最高的字段**。模型在每次对话中都能看到所有 Skill 的 description，据此决定"当前问题需要读取哪些 Skill"。

### 正面路由

明确列出该 Skill 适用的场景：

```yaml
description: >-
  Use this skill whenever the user asks about orders, purchases, sales, or
  transaction history. Join to customers via customer_id and to books via
  book_id.
```

关键词要覆盖用户可能的表述方式——"orders"、"purchases"、"sales"、"transaction" 都指向同一张表。

### 负面路由

有些表容易与其他表混淆，需要主动"劝退"：

```yaml
description: >-
  Use this skill ONLY when the user explicitly asks about platform users —
  login accounts, SSO ids, roles. This table is unrelated to the enterprise
  tables. Most questions about "用户" actually mean enterprises, not
  platform users — confirm with the user if ambiguous.
```

两个关键表述：
- **`ONLY when ... explicitly asks about`**——设定明确的启用门槛
- **`Most questions about "用户" actually mean enterprises`**——给模型消歧策略

### 反模式

| 写法 | 问题 | 改进 |
|---|---|---|
| `"关于图书的信息"` | 太笼统，所有问题都可能"关于图书" | `"Use when user asks about book titles, authors, genres, prices, stock, or publishers"` |
| `"订单表"` | 纯标签，没有路由信息 | `"Use when user asks about orders, purchases, sales, or transaction history"` |
| `"包含 id, customer_id, book_id..."` | 把 Schema 塞进 description 浪费 token | description 只放路由提示，Schema 放正文 |

---

## D. 数据库场景的 Skill 编写要点

### 整理每张表的信息

编写 Skill 前，先回答三个问题：

1. **这张表是什么**——一句话描述表的内容
2. **什么问题需要用到它**——典型的用户问题
3. **有哪些坑**——类型不一致、枚举值、需要排除的状态

### 常见 Gotchas 模式

在数据库 Agent 场景中，以下几类"坑"反复出现：

| 模式 | 说明 | SKILL.md 中如何写 |
|---|---|---|
| **TEXT 当数字存** | `price`、`register_capital` 等字段用 TEXT 存储数字。直接 `ORDER BY` 会按字符串排序（"99" 排在 "1000" 前面） | Schema 列紧邻标注 `**TEXT**, use CAST(... AS REAL)`；Gotchas 再次强调 |
| **状态过滤** | 聚合查询需排除某些状态（如 `已取消` 的订单不应计入收入） | Gotchas 明确写 `Exclude status = '已取消' from revenue calculations` |
| **预计算字段** | `total_price` 已是 `quantity × unit_price` 的结果，不需要也不应该重新计算 | Gotchas 写明 `total_price is pre-computed, don't re-multiply` |
| **Join 关系** | 跨表查询需要知道 join key | Schema 中用 FK 标注，description 中也提到 `Join to X via column` |
| **枚举值中文** | `genre` 的值是 `文学`、`科幻` 而非 `Literature`、`Sci-Fi` | Common values 列出所有可能值 |
| **日期格式** | 日期存为 TEXT（如 `2025-01-15`），需要 `date()` 或 `strftime()` 处理 | Schema 标注格式，Gotchas 说明用法 |

---

## E. 完整示例

以下是书店数据库三个表的 SKILL.md，完整且可直接使用。

### `skills/books/SKILL.md`

````markdown
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
| `price` | TEXT | 价格（元）— **TEXT not numeric**, use `CAST(price AS REAL)` |
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

## Gotchas

- `price` is **TEXT**, not REAL — always `CAST(price AS REAL)` for numeric ops.
- `genre` uses Chinese category names. For fuzzy search use `LIKE '%技术%'`.
- `publish_year` is INTEGER and can be used directly in comparisons.
````

### `skills/orders/SKILL.md`

````markdown
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

**Top customers by spend:**

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

## Gotchas

- `total_price` is **TEXT** — always `CAST(total_price AS REAL)`.
- Exclude `status = '已取消'` from revenue calculations.
- `total_price` is pre-computed. Don't re-multiply `quantity * books.price`.
- `order_date` is TEXT in `YYYY-MM-DD` format. Use `strftime()` for grouping.
````

### `skills/customers/SKILL.md`

````markdown
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

**List 金卡 or above members:**

```sql
SELECT name, email, city, member_level
FROM customers
WHERE member_level IN ('金卡', '钻石')
ORDER BY name;
```

## Gotchas

- `member_level` hierarchy: `普通` < `银卡` < `金卡` < `钻石`. No numeric rank
  column — use `CASE WHEN` to impose ordering if needed.
- `created_at` uses ISO datetime. Use `date()` or `strftime()` for date arithmetic.
````

### 反模式对照表

| 反模式 | 后果 | 正确做法 |
|---|---|---|
| 不写 `description`，或写得太笼统 | 模型无法判断何时读取该 Skill，要么总读（浪费 token），要么不读（出错） | 写明"Use when user asks about X, Y, Z" |
| Schema 不标注 TEXT 类型陷阱 | 模型按数字处理 TEXT 列，排序/聚合结果错误 | 在 Type 列写 `TEXT`，Description 中加 `**TEXT**, use CAST(...)` |
| Example queries 用伪代码 | 模型学到错误的 SQL 模式 | 每个示例必须是可直接运行的完整 SQL |
| 不写 Gotchas | 模型踩同样的坑——错误排序、漏排除取消订单、重复计算 | 把你知道的每一个"坑"都写出来 |
| 把所有表的 Schema 塞进 system prompt | system prompt 膨胀至数千行，浪费 token，干扰模型 | Schema 放 Skill 正文，system prompt 只保留工作流 |

---

## F. 层级化 Skill（进阶）

当数据库有很多张表时，可以用**目录嵌套**来组织 Skill：

```
skills/
├── SKILL.md                    # 顶层索引：简介所有子目录
├── enterprise/
│   ├── SKILL.md                # enterprise 组索引
│   ├── basic/SKILL.md          # enterprise_basic 表
│   ├── contact/SKILL.md        # enterprise_contact 表
│   ├── financing/SKILL.md      # enterprise_financing 表
│   └── product/SKILL.md        # enterprise_product 表
├── industry/
│   ├── SKILL.md                # industry 组索引
│   ├── chain/SKILL.md          # industry 表（产业链节点）
│   └── mapping/SKILL.md        # industry_enterprise 表（映射关系）
└── platform/
    └── users/SKILL.md          # users 表
```

**层级化的好处**：

- 父级 `SKILL.md` 做**索引和路由**——其 `description` 告诉模型"这组 Skill 涉及企业信息"，正文列出子 Skill 的清单
- 模型先读取父级，根据索引决定具体读取哪个子 Skill
- 避免 20+ 个 Skill 的 description 同时出现在 context 中，降低干扰

**何时需要层级化**：

- 5 张表以下：平铺即可，不需要层级
- 5-15 张表：按业务领域分组，加父级索引
- 15 张表以上：强烈建议层级化，否则 description 列表过长

---

## 小结

| 要点 | 说明 |
|---|---|
| Skill = 文件夹 + SKILL.md | 与 Claude Skills 完全兼容 |
| `description` 是路由标签 | 写得精准 → 模型路由正确；写得含糊 → 模型出错 |
| 正文按需加载 | 不浪费 token，不干扰无关查询 |
| Gotchas 是核心价值 | 你的领域经验决定 Agent 的准确率 |
| 用负面路由防误用 | "Do NOT use when..." 比"Use when..."同等重要 |
| 表多时层级化组织 | 父级做索引，子级放详情 |

→ 下一章：[第 3 章 · 编写 System Prompt](./03-system-prompt.md)
