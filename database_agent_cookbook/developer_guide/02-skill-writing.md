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

## D. 数据库场景：用 Skill 提升问答准确率

数据库 Agent 的准确率取决于模型能否写出**正确的 SQL**。模型犯错通常不是因为"不会写 SQL"，而是因为**不了解这个数据库的具体情况**——字段类型、业务含义、数据分布、表间关系。Skill 的作用就是补上这些信息。

本节系统讲解如何针对数据库场景编写 Skill，使 Agent 的问答准确率最大化。

### D.1 编写前：审计你的数据库

在动手写 SKILL.md 之前，先对数据库做一次"审计"，逐表回答以下问题：

| 审计项 | 问题 | 对应 Skill 章节 |
|---|---|---|
| **表的业务含义** | 这张表存的是什么？一行代表什么？ | 标题 + 开头描述 |
| **主键和外键** | 表之间怎么 join？ | Schema（PK/FK 标注）+ description |
| **类型陷阱** | 哪些列的存储类型和业务含义不匹配？（TEXT 存数字、TEXT 存日期） | Schema（紧邻标注）+ Gotchas |
| **枚举值** | 哪些列只有有限的几个取值？取值是中文还是英文？ | Common values |
| **业务规则** | 聚合时需要排除哪些状态？哪些字段是预计算的？ | Gotchas |
| **常见查询模式** | 用户最常问什么？正确的 SQL 怎么写？ | When to use + Example queries |
| **易混淆的表** | 哪些表名/列名容易被混淆？ | description（负面路由） |

**每回答一个问题，就往 SKILL.md 里加一条信息。** 审计做完，Skill 也基本写完了。

### D.2 类型陷阱：准确率的第一杀手

数据库中最常见的准确率问题是**类型不匹配**——字段的存储类型和业务含义不一致。

#### TEXT 存数字

这是出现频率最高的陷阱。很多数据库把金额、数量、比例等数值用 TEXT 类型存储：

```
price = "168.00"     -- TEXT，不是 REAL
register_capital = "5000"  -- TEXT，不是 INTEGER
```

**不写 Skill 时的后果**：

用户问"价格最高的 5 本书"，模型写出：

```sql
SELECT title, price FROM books ORDER BY price DESC LIMIT 5;
```

这条 SQL 按**字符串排序**：`"99.00" > "89.00" > "79.00" > "68.00" > "55.00"`——真正最贵的 `"168.00"` 排在后面，因为字符 `"1"` 小于 `"5"`。结果完全错误，但看起来像是对的，很难被发现。

**Skill 如何解决**：

在 Schema 表中紧邻列名标注：

```markdown
| `price` | TEXT | 价格（元）— **TEXT not numeric**, use `CAST(price AS REAL)` |
```

在 Example queries 中展示正确写法：

```sql
SELECT title, CAST(price AS REAL) AS price_yuan
FROM books
ORDER BY price_yuan DESC
LIMIT 5;
```

在 Gotchas 中再次强调：

```markdown
- `price` is **TEXT** — always `CAST(price AS REAL)` for numeric operations.
  Direct `ORDER BY price` gives wrong results (string sort: "99" > "168").
```

**三处提示的原因**：Schema 表让模型在"扫一眼"时就注意到类型；Example queries 提供正确的 SQL 模板；Gotchas 解释为什么错以及错在哪里。三层信息互相加强，确保模型不会遗漏。

#### TEXT 存日期

日期存为 TEXT（如 `"2025-01-15"`）时，模型可能不知道如何做日期运算：

```markdown
## Gotchas

- `order_date` is TEXT in `YYYY-MM-DD` format, not a DATE type.
  - Filter by month: `WHERE order_date LIKE '2025-03%'` or
    `WHERE strftime('%Y-%m', order_date) = '2025-03'`
  - Filter by range: `WHERE order_date BETWEEN '2025-01-01' AND '2025-03-31'`
  - Group by month: `strftime('%Y-%m', order_date)`
```

提供多种常用写法，模型可以根据具体场景选择。

#### 隐式的枚举等级

`member_level` 存的是 `普通`/`银卡`/`金卡`/`钻石`，人类知道这是有等级的，但模型不知道。用户问"金卡及以上的会员"时，模型可能只查 `= '金卡'` 而遗漏 `钻石`。

```markdown
## Gotchas

- `member_level` has an implicit hierarchy: `普通` < `银卡` < `金卡` < `钻石`.
  There is no numeric rank column.
  - "金卡及以上": `WHERE member_level IN ('金卡', '钻石')`
  - For ordering by level: use `CASE WHEN member_level = '钻石' THEN 4
    WHEN member_level = '金卡' THEN 3 WHEN member_level = '银卡' THEN 2
    ELSE 1 END`
```

### D.3 业务规则：Gotchas 的核心

类型陷阱靠看 Schema 就能发现，但**业务规则**只有了解业务的人才知道。这正是 Skill 不可替代的价值。

#### 状态过滤

几乎所有有"状态"字段的表都需要写明哪些状态应在聚合中排除：

```markdown
## Gotchas

- `status` = `已取消` should be **excluded** from:
  - Revenue calculations (`SUM(total_price)`)
  - Order count statistics (`COUNT(*)`)
  - Customer purchase history
- Only include `已取消` when the user explicitly asks about cancellations.
```

不写这条，模型计算"2025 年 3 月总收入"时会把已取消的订单也算进去，金额偏高。用户不会意识到结果有误，因为模型会自信地给出一个看似合理的数字。

#### 预计算字段

```markdown
## Gotchas

- `total_price` is **pre-computed** (= quantity × unit price at order time).
  Do NOT re-calculate as `quantity * books.price` because:
  - Unit price may have changed since the order was placed
  - Discounts/promotions are already factored into `total_price`
  - Re-multiplication will produce incorrect results
```

#### 业务术语映射

用户说的"收入"、"销售额"、"营业额"可能都指同一个计算；"客单价"是总金额除以客户数而非订单数。这类映射需要在 Skill 中说明：

```markdown
## Gotchas

- "收入"/"销售额"/"营业额" = `SUM(CAST(total_price AS REAL)) WHERE status != '已取消'`
- "客单价" = total revenue / number of unique customers (not order count)
- "复购率" = customers with 2+ orders / total customers
```

### D.4 跨表查询：用 description 和 Schema 引导 Join

用户的问题往往涉及多张表："买了科幻书的客户有哪些？"需要 join `orders`、`books`、`customers`。模型能否写出正确的 join，取决于 Skill 中是否清楚标注了表间关系。

#### 在 description 中标注 join 关系

```yaml
# orders/SKILL.md
description: >-
  Use this skill whenever the user asks about orders, purchases, sales, or
  transaction history. Join to customers via customer_id and to books via
  book_id.
```

`Join to customers via customer_id` 这句话同时告诉模型两件事：(1) orders 表和 customers 表有关联，(2) join key 是 `customer_id`。

#### 在 Schema 中标注 FK

```markdown
| `customer_id` | INTEGER FK | → `customers.id` |
| `book_id`     | INTEGER FK | → `books.id` |
```

箭头写法 `→ customers.id` 比纯文字"外键关联到 customers 表"更直观。

#### 在 Example queries 中提供 join 示例

```sql
-- "哪个客户消费最多？"需要 join orders + customers
SELECT c.name, COUNT(*) AS order_count,
       SUM(CAST(o.total_price AS REAL)) AS total_spent
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status != '已取消'
GROUP BY c.id
ORDER BY total_spent DESC
LIMIT 5;
```

**关键**：join 示例中要同时展示正确的 join 条件和业务过滤条件（`status != '已取消'`）。模型会模仿这个模式来写新的 join 查询。

#### 用"跨表引用"防止 Skill 孤立

在 orders 的 Skill 中提醒模型：

```markdown
**This table is for transactional data.** For customer details (name, city,
member_level), use `customers`. For book details (title, author, genre),
use `books`.
```

这告诉模型：如果用户问的信息不在 orders 表里（比如"客户来自哪个城市"），需要读取另一个 Skill 并做 join，而不是在 orders 表里找一个不存在的列。

### D.5 Example queries 的选择策略

Example queries 是模型编写 SQL 的直接模板。选择哪些查询作为示例，直接影响准确率。

#### 选择原则

1. **覆盖最常见的查询模式**——聚合（SUM/COUNT/AVG）、排序（ORDER BY）、分组（GROUP BY）、筛选（WHERE）、join
2. **每个示例至少展示一个"坑"的正确处理方式**——CAST、状态过滤、日期处理
3. **选择用户真的会问的问题**——不要写没人会问的查询

#### 示例数量

- 每张表 2-4 个示例为宜
- 太少（0-1 个）：模型缺少 few-shot 模板，靠猜测编写 SQL
- 太多（5+ 个）：Skill 正文过长，增加 token 消耗，且模型可能忽略后面的示例

#### 好示例 vs 差示例

| 好示例 | 差示例 |
|---|---|
| 涉及类型转换的聚合查询（展示 CAST 的正确用法） | 简单的 `SELECT * FROM table LIMIT 10` |
| 带 WHERE 过滤的分组统计（展示状态过滤 + GROUP BY） | 不带 WHERE 的全表查询 |
| 多表 join 查询（展示 join key + 别名用法） | 单表单列查询 |
| 日期范围查询（展示 strftime 用法） | 不涉及任何"坑"的查询 |

### D.6 诊断与迭代：Skill 写完后怎么验证

写完 Skill 不代表结束。用以下方法验证和改进：

#### 用 "When to use" 中的问题测试

每个 Skill 的 "When to use" 列出了 3-5 个典型问题。把这些问题逐一输入 Agent，检查：

1. 模型是否读取了正确的 Skill？（如果没读取，说明 description 路由不够精准）
2. SQL 是否正确？（如果类型处理错误，说明 Schema/Gotchas 描述不够醒目）
3. 结果是否符合预期？（如果结果偏差，检查业务规则是否写全了）

#### 测试容易出错的问题

除了典型问题，刻意测试边界情况：

- 涉及 TEXT 数字列的排序/聚合："价格最高的书"、"总收入是多少"
- 需要排除特定状态的查询："3 月的收入"（是否排除了已取消订单）
- 跨表查询："北京的客户买了哪些书"（需要三表 join）
- 涉及隐式等级的查询："金卡及以上的会员"（是否包含了钻石）
- 模糊表述的查询："销量最好的书"（是按订单数还是按数量？）

#### 根据错误迭代 Skill

每次 Agent 回答错误，分析根因并更新 Skill：

| Agent 的错误 | 根因 | Skill 如何修改 |
|---|---|---|
| 没有读取该 Skill | description 不够精准，缺少关键词 | 在 description 中加入用户使用的关键词 |
| 列名写错 | Schema 不完整或不够醒目 | 补全列名，加粗关键列 |
| 类型处理错误 | Gotchas 提示不够强 | Schema 标注 + Gotchas + Example queries 三处同时加提示 |
| 漏排除某状态 | 业务规则没写 | 在 Gotchas 中加入过滤规则 |
| Join 写错 | FK 关系不清楚 | Schema 标注 FK，description 加 join 说明 |
| 业务术语理解错 | 缺少术语映射 | 在 Gotchas 中加入"X = Y"的映射 |

**Skill 是活文档**——随着你发现更多问题，持续补充 Gotchas 和 Example queries。每修复一个错误就加一条对应的提示，Agent 的准确率会逐步提升。

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
