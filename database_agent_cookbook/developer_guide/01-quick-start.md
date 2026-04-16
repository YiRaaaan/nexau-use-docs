# 第 1 章 · 快速开始：5 分钟跑起来一个数据库 Agent

> **目标**：用 3 个文件创建并部署一个能回答数据库问题的 Agent。
>
> **前置条件**：
> - NAC CLI 已安装
> - 数据库已接入平台（SQL 查询是内置工具，无需自行开发）
> - 已配置 LLM 环境变量（`LLM_MODEL`、`LLM_BASE_URL`、`LLM_API_KEY`）

---

## 你只需要 3 个文件

```
my_agent/
├── agent.yaml          # Agent 配置
├── system_prompt.md    # 系统提示词
└── skills/
    └── my_table/
        └── SKILL.md    # 表的领域知识
```

没有 Python 代码、没有工具实现、没有 middleware。SQL 查询工具由平台内置提供。

---

## Step 1：创建 `agent.yaml`

```yaml
type: agent
name: my_db_agent
description: 回答关于数据库的自然语言问题。

system_prompt: ./system_prompt.md
system_prompt_type: file
max_iterations: 50
tool_call_mode: structured

llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: openai_chat_completion
  temperature: 0.2
  stream: true

skills:
  - ./skills/my_table
```

**关键点**：
- 无需 `tools:` 段——SQL 查询由平台内置工具 `execute_sql` 提供
- `skills:` 指向 Skill 文件夹（不是 SKILL.md 文件本身）
- `${env.VAR}` 语法会在启动时从环境变量读取实际值

## Step 2：创建 `system_prompt.md`

```markdown
You are a database agent. Your job: translate natural-language questions into
correct SQL, execute the query, and return a clear answer grounded in the
actual data.

## Database

- Engine: SQLite (read-only via `execute_sql`)
- Tables: `my_table`

**Detailed schema and example queries are provided as Skills — one Skill per
table. ALWAYS read the relevant Skill before writing a query.**

## Workflow

1. **Plan.** Identify which tables you need.
2. **Read Skills.** Read the Skill for every table you plan to touch.
3. **Write the SQL.** Always use `LIMIT`.
4. **Execute.** Call `execute_sql`.
5. **Reflect.** If 0 rows returned, re-read the Skill and try again.
6. **Answer** in the user's language. Show key data and the SQL used.

## Constraints

- Only SELECT queries are allowed.
- Don't guess column names — check the Skill first.
```

## Step 3：创建 `skills/my_table/SKILL.md`

````markdown
---
name: my_table
description: >-
  Use this skill when the user asks about ... (写明适用场景)
---

# my_table — 表描述

## When to use

- "典型问题 1"
- "典型问题 2"

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | 主键 |
| `name` | TEXT | 名称 |
| ... | ... | ... |

## Example queries

```sql
SELECT name FROM my_table LIMIT 10;
```

## Gotchas

- （列出该表的注意事项）
````

## Step 4：部署

```bash
nac deploy
```

## Step 5：测试

向 Agent 提问，验证它能否正确回答。

---

## 试一试：发现问题

假设你的数据库有一个 `books` 表，其中 `price` 字段的类型是 **TEXT**（而非数字）。

如果你的 SKILL.md 只写了最简版本，没有标注类型陷阱：

```markdown
## Schema

| Column | Type | Description |
|---|---|---|
| `price` | TEXT | 价格 |
```

问 Agent："价格最高的 5 本书是什么？"

Agent 可能会写出：

```sql
SELECT title, price FROM books ORDER BY price DESC LIMIT 5;
```

这条 SQL 按**字符串排序**——"99.00" 会排在 "168.00" 前面，结果完全错误。

**怎么修？** 在 SKILL.md 中加上类型提示和正确的 SQL 示例：

```markdown
| `price` | TEXT | 价格（元）— **TEXT not numeric**, use `CAST(price AS REAL)` |
```

```sql
SELECT title, CAST(price AS REAL) AS price_yuan
FROM books ORDER BY price_yuan DESC LIMIT 5;
```

这就是 Skill 的价值——**把你对数据库的了解传递给模型**。

→ 详细了解如何编写高质量的 Skill：[第 2 章 · 编写 Skill](./02-skill-writing.md)

→ 详细了解 System Prompt 的编写方法：[第 3 章 · 编写 System Prompt](./03-system-prompt.md)

→ `agent.yaml` 各字段的完整说明：[第 4 章 · Agent 配置参考](./04-agent-config.md)
