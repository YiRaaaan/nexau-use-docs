# 第 2 章 · 编写 Skill：提升数据库 Agent 的问答准确率

> **本章是整个开发者指南的核心。**
>
> 数据库 Agent 答错，通常不是模型"不会写 SQL"，而是**不了解这个数据库的具体情况**——字段类型、业务含义、表间关系。Skill 的作用就是把你对数据库的了解传递给模型，让它写出正确的 SQL。
>
> 本章从"Agent 为什么会答错"出发，逐步教你如何编写 Skill 来解决这些问题。

---

## 1. 数据库 Agent 为什么会答错

来看一个真实的例子。书店数据库有一张 `books` 表，其中 `price` 字段用 **TEXT** 类型存储价格：

```
price = "168.00"   -- TEXT，不是 REAL
price = "36.00"
price = "99.00"
```

用户问"价格最高的 5 本书"，模型写出：

```sql
SELECT title, price FROM books ORDER BY price DESC LIMIT 5;
```

结果：`"99.00"` 排在 `"168.00"` 前面。因为 TEXT 按字符串排序，字符 `"9"` 大于 `"1"`。**结果完全错误，但看起来像是对的**——这种错误最危险，用户很难发现。

同样的问题在数据库中反复出现：

- 金额字段用 TEXT 存储 → 排序/聚合结果错误
- 聚合时没有排除"已取消"的订单 → 收入偏高
- 不知道 `total_price` 是预计算的 → 重新乘了一次 `quantity × price`，结果偏差
- 不知道表之间怎么 join → 列名猜错，查询报错

这些错误有一个共同特征：**模型的 SQL 语法完全正确，错在不了解这个数据库的"潜规则"**。

Skill 就是用来解决这个问题的——把"潜规则"写成模型能读到的文档。

---

## 2. Skill 的基本结构

在展开具体写法之前，先了解 Skill 长什么样。一个 Skill 就是一个**文件夹**里放一个 **`SKILL.md`**：

```
skills/
└── books/
    └── SKILL.md
```

`SKILL.md` 由两部分组成——开头的 frontmatter 和后面的正文：

```markdown
---
name: books
description: Use this skill whenever the user asks about books — titles,
  authors, genres, prices, stock, or publishers.
---

# books — 书籍目录
（正文：Schema、示例 SQL、注意事项...）
```

两部分的分工：

- **`description`**（始终对模型可见）——告诉模型"什么时候该读取这个 Skill"
- **正文**（模型决定读取时才加载）——告诉模型"这张表具体怎么查"

接下来的内容围绕一个核心问题展开：**正文里写什么、怎么写，才能让 Agent 答对？**

---

## 3. 第一步：审计你的数据库

编写 Skill 之前，先逐表做一次"审计"。对每张表回答以下问题：

| 问题 | 目的 |
|---|---|
| 这张表存的是什么？一行代表什么？ | 让模型理解表的业务含义 |
| 哪些列的存储类型和业务含义不匹配？ | 发现类型陷阱（TEXT 存数字、TEXT 存日期） |
| 哪些列只有几个固定取值？ | 列出枚举值，减少模型猜测 |
| 聚合时需要排除哪些数据？ | 明确业务过滤规则 |
| 哪些字段是预计算的？ | 防止模型重复计算 |
| 表之间怎么 join？ | 标注主键和外键关系 |
| 用户最常问什么问题？正确的 SQL 怎么写？ | 准备示例查询 |

**每回答一个问题，就往 SKILL.md 里写一条。** 审计做完，Skill 也基本写完了。

---

## 4. 类型陷阱：准确率的第一杀手

### TEXT 存数字

这是出现频率最高的问题。金额、注册资本、比例等数值用 TEXT 存储，在很多数据库中都存在。

**Skill 中需要在三个地方提示**：

**Schema 表——紧邻列名标注**：

```markdown
| Column | Type | Description |
|---|---|---|
| `price` | TEXT | 价格（元）— **TEXT not numeric**, use `CAST(price AS REAL)` |
```

模型读 Schema 时一眼就能看到类型警告。

**Example queries——展示正确写法**：

```sql
SELECT title, CAST(price AS REAL) AS price_yuan
FROM books
ORDER BY price_yuan DESC
LIMIT 5;
```

模型会模仿示例的模式来写新查询。

**Gotchas——解释为什么错**：

```markdown
- `price` is **TEXT** — always `CAST(price AS REAL)` for numeric operations.
  Direct `ORDER BY price` gives wrong results (string sort: "99" > "168").
```

三处信息互相加强：Schema 让模型注意到类型，Example 提供正确模板，Gotchas 解释原因。单写一处可能被忽略，三处一起写才可靠。

### TEXT 存日期

日期存为 TEXT（如 `"2025-01-15"`）时，模型可能不知道如何做日期运算。在 Gotchas 中提供常用写法：

```markdown
- `order_date` is TEXT in `YYYY-MM-DD` format, not a DATE type.
  - Filter by month: `WHERE order_date LIKE '2025-03%'` or
    `WHERE strftime('%Y-%m', order_date) = '2025-03'`
  - Filter by range: `WHERE order_date BETWEEN '2025-01-01' AND '2025-03-31'`
  - Group by month: `strftime('%Y-%m', order_date)`
```

### 隐式的枚举等级

`member_level` 的值是 `普通`/`银卡`/`金卡`/`钻石`，人类知道这是有等级高低的，但模型不知道。用户问"金卡及以上的会员"时，模型可能只查 `= '金卡'` 而遗漏 `钻石`：

```markdown
- `member_level` has an implicit hierarchy: `普通` < `银卡` < `金卡` < `钻石`.
  There is no numeric rank column.
  - "金卡及以上": `WHERE member_level IN ('金卡', '钻石')`
  - For ordering by level: use `CASE WHEN member_level = '钻石' THEN 4
    WHEN member_level = '金卡' THEN 3 WHEN member_level = '银卡' THEN 2
    ELSE 1 END`
```

---

## 5. 业务规则：只有你知道的知识

类型陷阱靠看 Schema 就能发现，但**业务规则只有了解业务的人才知道**。这是 Skill 不可替代的价值——你把业务经验写进去，Agent 就能用上。

### 状态过滤

几乎所有有"状态"字段的表都需要写明过滤规则：

```markdown
## Gotchas

- `status` = `已取消` should be **excluded** from:
  - Revenue calculations (`SUM(total_price)`)
  - Order count statistics (`COUNT(*)`)
  - Customer purchase history
- Only include `已取消` when the user explicitly asks about cancellations.
```

不写这条，模型计算"2025 年 3 月总收入"时会把已取消的订单也算进去。用户不会意识到结果有误，因为模型会自信地给出一个看似合理的数字。

### 预计算字段

```markdown
- `total_price` is **pre-computed** (= quantity × unit price at order time).
  Do NOT re-calculate as `quantity * books.price` because:
  - Unit price may have changed since the order was placed
  - Discounts/promotions are already factored into `total_price`
  - Re-multiplication will produce incorrect results
```

### 业务术语映射

用户说"收入"、"销售额"、"营业额"可能都指同一个计算；"客单价"是总金额除以客户数而非订单数。如果不写明，模型只能猜：

```markdown
- "收入"/"销售额"/"营业额" = `SUM(CAST(total_price AS REAL)) WHERE status != '已取消'`
- "客单价" = total revenue / number of unique customers (not order count)
- "复购率" = customers with 2+ orders / total customers
```

### 数据边界

有些列有特殊的数据情况需要提前说明：

```markdown
- `zhuanjingtexin_level` 可能为 NULL — 大部分企业没有专精特新认证，
  查询时用 `WHERE zhuanjingtexin_level IS NOT NULL`
- `enterprise_name` in mock data are all `测试企业_N`, not real company names
- `industry_level1` may have numeric prefix (e.g. `26 化学原料和化学制品制造业`),
  use `LIKE '%制造%'` for fuzzy matching
```

---

## 6. 跨表查询：引导模型正确 Join

用户的问题经常涉及多张表——"买了科幻书的客户有哪些？"需要同时查 `orders`、`books`、`customers`。模型能否写出正确的 join，取决于你是否在 Skill 中清楚标注了表间关系。

### 在 description 中标注 join 关系

```yaml
description: >-
  Use this skill whenever the user asks about orders, purchases, sales, or
  transaction history. Join to customers via customer_id and to books via
  book_id.
```

`Join to customers via customer_id` 同时告诉模型两件事：(1) orders 和 customers 有关联，(2) join key 是 `customer_id`。

### 在 Schema 中标注 FK

```markdown
| `customer_id` | INTEGER FK | → `customers.id` |
| `book_id`     | INTEGER FK | → `books.id` |
```

箭头写法 `→ customers.id` 比纯文字"外键关联到 customers 表"更直观，模型一眼能看懂。

### 在 Example queries 中提供 join 示例

```sql
-- "哪个客户消费最多？"
SELECT c.name, COUNT(*) AS order_count,
       SUM(CAST(o.total_price AS REAL)) AS total_spent
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status != '已取消'
GROUP BY c.id
ORDER BY total_spent DESC
LIMIT 5;
```

join 示例中**同时展示 join 条件和业务过滤条件**（`status != '已取消'`）。模型会模仿这个模式来写新的 join 查询，两个条件都会带上。

### 用"跨表引用"防止 Skill 孤立

在 orders 的 Skill 中提醒模型去哪里找其他信息：

```markdown
**This table is for transactional data.** For customer details (name, city,
member_level), use `customers`. For book details (title, author, genre),
use `books`.
```

这告诉模型：如果用户问的信息不在 orders 表里（比如"客户来自哪个城市"），需要读取另一个 Skill 并做 join，而不是在 orders 表里猜一个不存在的列名。

---

## 7. Example queries：选什么、怎么选

Example queries 是模型编写 SQL 的直接模板。选对了示例，模型能举一反三；选错了，等于没写。

### 选择原则

1. **覆盖该表最常见的查询模式**——聚合（SUM/COUNT/AVG）、排序（ORDER BY）、分组（GROUP BY）、筛选（WHERE）、join
2. **每个示例至少展示一个"坑"的正确处理方式**——CAST、状态过滤、日期处理
3. **选择用户真的会问的问题**

### 每张表 2-4 个示例

- 太少（0-1 个）：模型缺少模板，靠猜测编写 SQL
- 太多（5+ 个）：Skill 正文过长，模型可能忽略后面的示例

### 好示例 vs 差示例

| 好示例 | 差示例 |
|---|---|
| 涉及类型转换的聚合查询（展示 CAST） | `SELECT * FROM table LIMIT 10` |
| 带 WHERE 过滤的分组统计（展示状态过滤 + GROUP BY） | 不带 WHERE 的全表扫描 |
| 多表 join（展示 join key + 表别名） | 单表单列简单查询 |
| 日期范围查询（展示 strftime） | 不涉及任何"坑"的查询 |

差示例的问题：模型已经会写简单查询了，不需要你教。**示例要展示的是模型自己不知道的东西**——类型转换、过滤规则、join 方式。

### 示例必须可直接运行

每个示例必须是完整的 SQL，不是伪代码。模型会原样模仿：

```sql
-- 好：完整可运行
SELECT title, CAST(price AS REAL) AS price_yuan
FROM books
ORDER BY price_yuan DESC
LIMIT 5;

-- 差：伪代码，模型不知道怎么填
SELECT ... FROM books WHERE <条件> ORDER BY <价格降序>;
```

---

## 8. description：让模型找到正确的 Skill

`description` 决定了模型在面对用户问题时"是否读取这个 Skill"。它始终对模型可见（不像正文是按需加载的），所以写法很关键。

### 正面路由：覆盖用户的表述方式

```yaml
description: >-
  Use this skill whenever the user asks about orders, purchases, sales, or
  transaction history. Join to customers via customer_id and to books via
  book_id.
```

"orders"、"purchases"、"sales"、"transaction" 都指向同一张表——关键词要覆盖用户可能的不同说法。

### 负面路由：主动劝退

有些表容易与其他表混淆。比如 `users` 表存的是平台账号，但用户说"用户"时大概率指的是客户或企业：

```yaml
description: >-
  Use this skill ONLY when the user explicitly asks about platform users —
  login accounts, SSO ids, roles. This table is unrelated to the enterprise
  tables. Most questions about "用户" actually mean enterprises, not
  platform users — confirm with the user if ambiguous.
```

两个要点：
- **`ONLY when ... explicitly asks about`**——设定高启用门槛
- **`Most questions about "用户" actually mean enterprises`**——给模型消歧策略

### description 反模式

| 写法 | 问题 | 改进 |
|---|---|---|
| `"关于图书的信息"` | 太笼统 | `"Use when user asks about book titles, authors, genres, prices, stock, or publishers"` |
| `"订单表"` | 纯标签，没有路由信息 | `"Use when user asks about orders, purchases, sales, or transaction history"` |
| `"包含 id, customer_id, book_id..."` | 把 Schema 塞进 description | description 只放路由提示，Schema 放正文 |

---

## 9. 测试与迭代

写完 Skill 不代表结束。Skill 的质量需要通过测试来验证，通过迭代来提升。

### 用典型问题测试

每个 Skill 的 "When to use" 中列出了典型问题，把这些问题逐一输入 Agent，检查：

1. 模型是否读取了正确的 Skill？（没读取 → description 路由不够精准）
2. SQL 是否正确？（类型处理错误 → Schema/Gotchas 描述不够醒目）
3. 结果是否符合预期？（偏差 → 业务规则没写全）

### 刻意测试边界情况

- 涉及 TEXT 数字列的排序/聚合："价格最高的书"、"总收入是多少"
- 需要排除特定状态的查询："3 月的收入"（是否排除了已取消订单）
- 跨表查询："北京的客户买了哪些书"（需要三表 join）
- 涉及隐式等级的查询："金卡及以上的会员"（是否包含了钻石）
- 模糊表述的查询："销量最好的书"（是按订单数还是按数量？）

### 错误 → 根因 → 修改 Skill

| Agent 的错误 | 根因 | Skill 如何修改 |
|---|---|---|
| 没有读取该 Skill | description 缺少关键词 | 在 description 中加入用户使用的关键词 |
| 列名写错 | Schema 不完整 | 补全列名 |
| 类型处理错误 | 提示不够强 | Schema + Gotchas + Example 三处同时加提示 |
| 漏排除某状态 | 业务规则没写 | 在 Gotchas 中加入过滤规则 |
| Join 写错 | FK 关系不清楚 | Schema 标注 FK，description 加 join 说明 |
| 业务术语理解错 | 缺少术语映射 | 在 Gotchas 中加入术语定义 |

**Skill 是活文档**——每次 Agent 答错，分析根因，加一条对应的提示。准确率会逐步提升。

---

## 10. 完整示例

以下是书店数据库三个表的 SKILL.md。注意观察每个 Skill 如何运用前面讲到的技巧——类型标注、业务规则、join 引导、示例选择。

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

---

## 11. 反模式速查

| 反模式 | 后果 | 正确做法 |
|---|---|---|
| Schema 不标注 TEXT 类型陷阱 | 排序/聚合结果错误 | Type 列写 `TEXT`，Description 加 `**TEXT**, use CAST(...)` |
| 不写 Gotchas | 模型反复踩坑 | 把你知道的每一个"坑"都写出来 |
| Example queries 用伪代码 | 模型学到错误的 SQL 模式 | 每个示例必须是可直接运行的完整 SQL |
| description 太笼统 | 模型无法判断何时读取 | 写明"Use when user asks about X, Y, Z" |
| 把所有表 Schema 塞进 system prompt | token 浪费，干扰模型 | Schema 放 Skill 正文，system prompt 只放工作流 |
| 不写 join 关系 | 跨表查询出错 | Schema 标注 FK，description 提到 join key |
| 不写业务术语定义 | "收入"是否含退款？"客单价"除以什么？ | Gotchas 中加术语映射 |

---

## 12. 层级化 Skill（进阶）

当数据库有很多张表时，用**目录嵌套**来组织：

```
skills/
├── SKILL.md                    # 顶层索引
├── enterprise/
│   ├── SKILL.md                # enterprise 组索引
│   ├── basic/SKILL.md
│   ├── contact/SKILL.md
│   ├── financing/SKILL.md
│   └── product/SKILL.md
├── industry/
│   ├── SKILL.md
│   ├── chain/SKILL.md
│   └── mapping/SKILL.md
└── platform/
    └── users/SKILL.md
```

- 父级 `SKILL.md` 做**索引**——模型先读父级，根据索引决定读哪个子 Skill
- 5 张表以下平铺即可；5-15 张按业务领域分组；15 张以上强烈建议层级化

---

→ 下一章：[第 3 章 · 编写 System Prompt](./03-system-prompt.md)
