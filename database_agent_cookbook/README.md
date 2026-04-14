# Database Agent Cookbook

> **一句话**：从任意 SQLite 数据库，5 分钟搭出一个能用自然语言查询的 NexAU Agent。

本 Cookbook 提供构建"数据库问答 Agent"所需的全部可复用组件：

| 组件 | 说明 |
|---|---|
| **通用 `execute_sql` 工具** | 三层安全的只读 SQL 执行器，适配任意 SQLite |
| **SKILL.md 模板** | 每张表一份，最佳实践格式 |
| **`generate_skills.py`** | ⭐ 一行命令，从数据库自动生成所有表的 SKILL.md |
| **system prompt 模板** | 数据库 Agent 专用工作流提示词 |
| **`agent.yaml` + `start.py`** | 开箱即用的 Agent 配置 |

---

## 目录结构

```
database_agent_cookbook/
├── README.md                           ← 你在这里
├── create_sample_db.py                 # 生成示例书店数据库
├── generate_skills.py                  # ⭐ 从任意 SQLite 自动生成 Skills
├── sample.sqlite                       # 示例数据库（运行 create_sample_db.py 后生成）
│
├── template/                           # 📦 可直接复制使用的 Agent 模板
│   ├── agent.yaml
│   ├── nexau.json
│   ├── system_prompt.md
│   ├── start.py
│   └── tools/
│       ├── execute_sql.py              # 通用 SQL 工具实现
│       ├── ExecuteSQL.tool.yaml        # SQL 工具 schema
│       └── TodoWrite.tool.yaml         # 规划工具 schema
│
├── skills_template/
│   └── SKILL.md.template              # SKILL.md 编写模板（含占位符）
│
└── examples/
    └── skills/                         # 基于示例书店数据库的完整 Skills
        ├── customers/SKILL.md
        ├── books/SKILL.md
        └── orders/SKILL.md
```

---

## 快速开始

### 1. 复制模板

```bash
cp -r database_agent_cookbook/template/ my_db_agent/
```

### 2. 准备数据库

将你的 `.sqlite` 文件放到项目中。本示例使用自带的书店数据库：

```bash
python database_agent_cookbook/create_sample_db.py
# → 生成 database_agent_cookbook/sample.sqlite（3 张表：customers, books, orders）
```

### 3. 自动生成 Skills

```bash
python database_agent_cookbook/generate_skills.py your_database.sqlite -o my_db_agent/skills
```

脚本会为每张表生成一个 `SKILL.md`，自动检测：
- ✅ 表结构（列名、类型、PK、FK）
- ✅ TEXT 列存数字（常见坑，如价格字段）
- ✅ 高 NULL 比例列
- ✅ 枚举型列的常见值
- ✅ FK 关系并生成 JOIN 示例

生成后需要人工补充的部分（标记为 `[TODO]`）：
- `description` 中的路由关键词
- "When to use" 的示例问题
- 业务含义说明
- 更多示例 SQL

### 4. 注册 Skills

编辑 `my_db_agent/agent.yaml`，取消 `skills:` 段的注释并填入路径：

```yaml
skills:
  - ./skills/customers
  - ./skills/books
  - ./skills/orders
```

### 5. 配置环境变量

```bash
# .env 文件
DB_PATH=./sample.sqlite
LLM_MODEL=your-model-name
LLM_BASE_URL=https://your-llm-api.com/v1
LLM_API_KEY=sk-xxx
```

### 6. 运行

```bash
uv run my_db_agent/start.py "哪本书最贵？"
```

---

## 组件详解

### 1. 通用 SQL 工具 — `execute_sql`

`template/tools/execute_sql.py` 是一个安全的只读 SQL 执行器，设计为适配**任意 SQLite 数据库**。

#### 三层安全

```
           ┌─────────────────────────┐
 Layer 1   │ 关键字白名单 + 黑名单    │  仅允许 SELECT / WITH 开头
           ├─────────────────────────┤
 Layer 2   │ SQL 注释剥离            │  防止 -- foo\nDELETE 绕过
           ├─────────────────────────┤
 Layer 3   │ file:...?mode=ro       │  SQLite 引擎级只读
           └─────────────────────────┘
```

任何一层被绕过，下一层仍能兜底。第三层 `mode=ro` 不依赖任何代码逻辑假设，是最终安全网。

#### 结构化返回

工具返回 JSON 对象而非纯文本字符串：

```json
{
  "status": "success",
  "columns": ["name", "city", "member_level"],
  "data": [{"name": "张三", "city": "北京", "member_level": "金卡"}],
  "total_rows": 10,
  "row_count": 5,
  "truncated": true,
  "warnings": ["Query results were truncated..."]
}
```

`warnings` 字段是给模型的"提示"——空结果时建议检查假设，截断时建议细化查询。这使工具结果从"答案"变为"一轮对话"。

#### 数据库路径

通过环境变量 `DB_PATH` 配置，无硬编码：

```python
DB_PATH_ENV = "DB_PATH"  # 环境变量名
```

#### 工具 Schema

`ExecuteSQL.tool.yaml` 是模型看到的"说明书"：

```yaml
type: tool
name: execute_sql
description: >-
  Execute a read-only SQL query against the connected database...
input_schema:
  type: object
  properties:
    sql:
      type: string
      description: The SQL query to execute (SELECT only).
    timeout:
      type: integer
      default: 30
    max_rows:
      type: integer
      default: 10
  required: [sql]
```

`description` 中的最佳实践（"Always use LIMIT"、"Use WHERE clauses"）直接影响模型行为——写在工具 schema 比写在 system prompt 更有效，因为模型每次决策时都会重新读到。

---

### 2. 数据库表 Skills 模板

Skills 是 NexAU 让模型"学习领域知识"的标准机制。每张数据库表对应一个 Skill。

#### SKILL.md 结构

```markdown
---
name: table_name                    ← 唯一标识
description: >-                     ← 路由提示（模型据此决定是否读取）
  Use this skill whenever ...
---

# table_name — 中文表名             ← 标题

## When to use                      ← 正面路由：何时读取
## Schema                           ← 表结构
## Common values                    ← 枚举值
## Example queries                  ← 示例 SQL（few-shot）
## Gotchas                          ← 坑点
```

#### 编写指南

**`description` 是路由，不是文档。** 它决定模型"看到用户问题后，是否需要读取该 Skill"。

```markdown
# ✅ 好的 description
description: >-
  Use this skill whenever the user asks about book prices, titles,
  authors, genres, stock levels, or publishers. Join to orders via book_id.

# ❌ 差的 description
description: >-
  Information about books.
```

**Gotchas 是最有价值的部分。** 模型犯错通常不是因为"不知道有这张表"，而是因为不知道：
- `price` 是 TEXT 不是数字
- `register_district` 和 `jurisdiction_district` 语义不同
- `status = '已取消'` 的行需要排除

**Example queries 就是 few-shot。** 提供完整、正确的 SQL 示例，模型会照着写。

#### 反模式

| 反模式 | 后果 |
|---|---|
| description 太笼统 | 模型路由出错，该读时不读、不该读时读了 |
| 不写 Gotchas | 模型重复踩 TEXT 当数字排序等坑 |
| Example queries 用 `SELECT *` | 模型也学着写 `SELECT *`，结果集过大 |
| 所有知识放 system prompt | 每次对话浪费 token，模型注意力分散 |
| 一个 Skill 塞多张表 | 路由粒度太粗，无法按需加载 |

---

### 3. 自动生成 Skills — `generate_skills.py`

这是 Cookbook 的核心工具。它连接任意 SQLite 数据库，为每张表自动生成一份 SKILL.md。

#### 用法

```bash
# 为所有表生成
python generate_skills.py mydb.sqlite -o ./skills

# 只生成指定表
python generate_skills.py mydb.sqlite --tables users,orders -o ./skills
```

#### 自动检测能力

| 检测项 | 描述 |
|---|---|
| 表结构 | 列名、类型、PK、NOT NULL、默认值 |
| 外键 | FK 关系，自动生成 JOIN 示例 |
| TEXT 存数字 | 采样前 20 行，>80% 是数字则标记为 Gotcha |
| 高 NULL 比例 | >30% NULL 时提醒 |
| 枚举型列 | ≤10 种不同值时列出 Common values |

#### 输出示例

对于 `books` 表，自动生成的 SKILL.md 会包含：

```markdown
## Gotchas

- `price` is **TEXT** but stores numeric values — use
  `CAST(price AS REAL)` for numeric comparisons and sorting.
```

这正是不经提醒时模型最容易犯错的地方。

#### 生成后必做的人工补充

脚本会在需要人工补充的地方留下 `[TODO]` 标记：

1. **`description` 路由关键词** — 哪些类型的问题应该触发读取该 Skill？
2. **"When to use" 示例问题** — 给出 3–5 个典型问题
3. **业务含义** — 列的中文名、枚举值的语义
4. **更多 Example queries** — 与你的业务场景匹配的 SQL

---

### 4. System Prompt 模板

`template/system_prompt.md` 是数据库 Agent 的系统提示词模板。核心工作流是 7 步：

```
Plan → Track tasks → Read Skills → Write SQL → Execute → Reflect → Answer
```

使用前需替换两个占位符：

| 占位符 | 替换为 |
|---|---|
| `{{TABLE_LIST}}` | 你的表名列表 |
| `{{JOIN_KEYS}}` | 你的表间 join key 关系 |

**关键设计**：

- **"ALWAYS read the relevant Skill before writing a query"** — 这一句必须保留。缺少它，模型会跳过读取 Skill 直接猜列名
- **Track tasks 仅对复杂问题启用** — "2+ tables OR multiple queries" 是触发条件；单表简单查询跳过，避免浪费
- **Reflect 步骤** — 模型看到 `total_rows == 0` 或 `warnings` 后必须反思而非直接回答

---

### 5. 规划工具 — `write_todos`

`TodoWrite.tool.yaml` 挂载 NexAU 内置的 `write_todos` 实现。它是模型的"草稿纸"——面对跨表查询时先列出步骤，逐步执行。

无需编写 Python 实现，`binding` 指向 NexAU 内置模块：

```yaml
binding: nexau.archs.tool.builtin.session_tools:write_todos
```

---

## 完整示例

### 用示例书店数据库跑一遍

```bash
# 1. 生成示例数据库
python database_agent_cookbook/create_sample_db.py

# 2. 复制模板
cp -r database_agent_cookbook/template/ bookstore_agent/

# 3. 自动生成 Skills
python database_agent_cookbook/generate_skills.py \
  database_agent_cookbook/sample.sqlite \
  -o bookstore_agent/skills

# 4. 用预写好的高质量示例 Skills 替换自动生成的（可选）
cp -r database_agent_cookbook/examples/skills/* bookstore_agent/skills/

# 5. 编辑 agent.yaml 注册 Skills
cat >> bookstore_agent/agent.yaml << 'EOF'

skills:
  - ./skills/customers
  - ./skills/books
  - ./skills/orders
EOF

# 6. 编辑 system_prompt.md 填入表信息
sed -i '' 's/{{TABLE_LIST}}/`customers`, `books`, `orders`/' bookstore_agent/system_prompt.md
sed -i '' 's/{{JOIN_KEYS}}/`orders.customer_id` → `customers.id`, `orders.book_id` → `books.id`/' bookstore_agent/system_prompt.md

# 7. 配置 .env 并运行
echo "DB_PATH=./database_agent_cookbook/sample.sqlite" >> .env
uv run bookstore_agent/start.py "哪个城市的客户最多？"
```

### 预期行为

模型会：
1. 读取 `customers` Skill（因为问题涉及"城市"和"客户"）
2. 编写正确的 SQL：`SELECT city, COUNT(*) AS n FROM customers GROUP BY city ORDER BY n DESC`
3. 返回回答 + SQL

### 对比：有 Skills vs 无 Skills

| 问题 | 无 Skills | 有 Skills |
|---|---|---|
| "哪本书最贵？" | `ORDER BY price DESC` ❌（TEXT 排序） | `ORDER BY CAST(price AS REAL) DESC` ✅ |
| "钻石会员有几个？" | 不知道 `member_level` 列 ❌ | 读取 Skill 后直接过滤 ✅ |
| "2025年3月收入多少？" | 不知道排除"已取消"订单 ❌ | Gotcha 提醒排除 `status='已取消'` ✅ |

---

## 适配其他数据库

本模板以 SQLite 为默认引擎。如需适配 MySQL / PostgreSQL / 其他数据库：

### 需要修改的文件

| 文件 | 修改内容 |
|---|---|
| `tools/execute_sql.py` | 替换 `sqlite3` 为目标数据库的 Python 驱动（如 `psycopg2`、`pymysql`）|
| `tools/ExecuteSQL.tool.yaml` | 更新 `description` 中的 SQL 方言说明 |
| `system_prompt.md` | 更新 "Engine: SQLite" 为目标数据库 |
| `generate_skills.py` | 替换 `PRAGMA table_info` 为 `information_schema` 查询 |

### 连接方式示例

```python
# PostgreSQL
import psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])

# MySQL
import pymysql
conn = pymysql.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    user=os.environ.get("DB_USER"),
    password=os.environ.get("DB_PASSWORD"),
    database=os.environ.get("DB_NAME"),
)
```

### 安全层调整

- SQLite 的 `mode=ro` 在其他数据库中需替换为**只读数据库用户**或 **`SET TRANSACTION READ ONLY`**
- 关键字白名单和注释剥离逻辑可通用保留

---

## 与教程的关系

本 Cookbook 是对 [主教程](../zh/README.md) 第 2–4 章内容的**提炼和泛化**：

| 主教程 | 本 Cookbook |
|---|---|
| 第 2 章：为企业数据库写 `execute_sql` | → 通用版 `execute_sql`（任意 SQLite） |
| 第 3 章：手写 7 个表的 Skills | → SKILL.md 模板 + `generate_skills.py` 自动生成 |
| 第 4 章：挂载 `write_todos` | → 包含在模板中，开箱即用 |

主教程适合**学习原理**（为什么这样设计），Cookbook 适合**快速复用**（换个数据库，5 分钟跑起来）。
