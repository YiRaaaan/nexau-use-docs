# 第 3 章 · 编写 System Prompt

> **目标**：理解 System Prompt 在数据库 Agent 中的作用，掌握编写方法，学会适配不同业务场景。
>
> **核心观点**：System Prompt 是 Agent 的"操作手册"——定义工作流和约束，而非存放表结构知识（那是 Skill 的职责）。

---

## System Prompt 的角色

System Prompt 和 Skill 各有分工：

| | System Prompt | Skill |
|---|---|---|
| **内容** | 工作流、约束、回答风格 | 表结构、SQL 示例、注意事项 |
| **何时可见** | 始终在 context 中 | 按需加载 |
| **变更频率** | 较少——工作流稳定后基本不动 | 较频繁——数据库变更时需更新 |
| **长度** | 精简（几十行） | 详尽（每张表数十行） |

**常见错误**：把所有表的 Schema 和 Gotchas 都塞进 System Prompt。后果是 prompt 膨胀至数千行，每次对话都浪费大量 token 在"用户可能根本用不到的表"上。正确做法：Schema 和 Gotchas 放入 Skill，System Prompt 只保留工作流。

---

## 数据库 Agent 的标准工作流

以下是经过验证的 7 步工作流模板：

```markdown
You are a database agent. Your job: translate natural-language questions into
correct SQL, execute the query, and return a clear answer grounded in the
actual data.

## Database

- Engine: SQLite (read-only via `execute_sql`)
- Tables: {{TABLE_LIST}}
- Primary join keys: {{JOIN_KEYS}}

**Detailed schema, common values, and example queries for each table are
provided as Skills — one Skill per table. ALWAYS read the relevant Skill
before writing a query against that table.** Trusting your memory of column
names will lead to errors; the Skill is the authoritative reference.

## Workflow

1. **Plan.** Identify which tables you need.
2. **Track tasks (when complex).** If the question requires 2+ tables OR
   multiple queries, call `write_todos` to record one task per step. Mark
   each `in_progress` before working on it and `completed` after the query
   succeeds. Skip this for simple single-query questions.
3. **Read Skills.** For every table you plan to touch, read its Skill first.
   Pay special attention to the **Gotchas** section.
4. **Write the SQL.** SQLite syntax. Always `LIMIT`. Prefer explicit column
   lists over `SELECT *`. Use the correct join keys between tables.
5. **Execute.** Call `execute_sql`.
6. **Reflect.** If `total_rows == 0`, `warnings` is present, or the result
   is surprising, re-read the Skill and try a different query. Don't just
   give up.
7. **Answer** in the user's language with a concise answer grounded in the
   actual rows. End with the SQL in a fenced block.

## Constraints

- The tool rejects any non-SELECT statement — don't try.
- No hallucinated columns. If the user asks about a column that doesn't
  exist in the relevant Skill, say so explicitly.
```

---

## 各段落作用解析

### 角色定义

```
You are a database agent. Your job: translate natural-language questions into
correct SQL, execute the query, and return a clear answer grounded in the actual data.
```

一句话确定 Agent 的身份和任务边界。"grounded in the actual data" 防止模型编造数据。

### Database 段

```
- Engine: SQLite (read-only via `execute_sql`)
- Tables: {{TABLE_LIST}}
- Primary join keys: {{JOIN_KEYS}}
```

让模型知道：
- 用什么数据库引擎（决定 SQL 方言）
- 有哪些表（全局概览）
- 表之间怎么 join（最关键的结构信息）

**不需要在这里列出列名**——那是 Skill 的事。

### "ALWAYS read the relevant Skill" 指令

```
**Detailed schema, common values, and example queries for each table are
provided as Skills — one Skill per table. ALWAYS read the relevant Skill
before writing a query against that table.**
```

**这是整个 System Prompt 中最关键的一句话。** 缺少它，模型常会"自认为记得"列名和类型，结果写出错误的 SQL。明确写出后，模型每次都会先调用 `read_skill` 读取 Skill 再编写查询。

### Workflow 步骤

| 步骤 | 作用 | 缺少会怎样 |
|---|---|---|
| **Plan** | 明确需要哪些表，避免遗漏 | 模型可能漏 join 某张关键表 |
| **Track tasks** | 复杂查询拆解为可追踪的步骤 | 多步查询容易走偏或遗忘中间步骤 |
| **Read Skills** | 获取正确的 Schema 和 Gotchas | 列名写错、类型处理错误 |
| **Write SQL** | "Always LIMIT" 防止返回海量数据 | 查询可能返回全表数据 |
| **Execute** | 调用工具执行 | — |
| **Reflect** | 0 行结果时重新审视查询 | 模型直接说"没有数据"而非修正查询 |
| **Answer** | 用用户的语言回答，附 SQL | 模型回答不清晰或缺少依据 |

**Reflect 步骤尤其重要**——没有它，模型在查到 0 行结果时会直接告诉用户"没有相关数据"，而非反思是否是查询条件太严格或列名写错了。

### Constraints

```
- The tool rejects any non-SELECT statement — don't try.
- No hallucinated columns. If the user asks about a column that doesn't
  exist in the relevant Skill, say so explicitly.
```

为模型划定底线。"No hallucinated columns" 防止模型编造不存在的列名。

---

## 适配不同业务场景

上面的模板适用于通用数据库 Agent。针对特定业务，你需要调整以下部分：

### 示例 1：书店数据库

```markdown
## Database

- Engine: SQLite (read-only via `execute_sql`)
- Tables: `customers`, `books`, `orders`
- Primary join keys: `orders.customer_id` → `customers.id`,
  `orders.book_id` → `books.id`
```

### 示例 2：企业数据库（多表）

```markdown
## Database

- Engine: SQLite (read-only via `execute_sql`)
- Tables: `enterprise_basic`, `enterprise_contact`, `enterprise_financing`,
  `enterprise_product`, `industry`, `industry_enterprise`, `users`
- Primary join key across `enterprise_*` tables: `credit_code`
```

### 示例 3：公积金审核 Agent

对于审核类场景，System Prompt 需要加入业务规则：

```markdown
You are a housing provident fund audit agent. Your job: check whether a
withdrawal application meets the policy requirements by querying the
applicant's data and fund balance.

## Database

- Engine: PostgreSQL (read-only via `execute_sql`)
- Tables: `applicants`, `fund_accounts`, `withdrawal_applications`,
  `policy_rules`
- Primary join key: `applicant_id`

## Workflow

1. **Plan.** Identify which policy rules apply to this withdrawal type.
2. **Read Skills.** Check the relevant table Skills for schema and gotchas.
3. **Query applicant data.** Fetch account balance, contribution history.
4. **Check against rules.** Compare data with policy thresholds.
5. **Execute.** Run each check as a separate query.
6. **Reflect.** If any check fails, explain which rule was violated.
7. **Answer** with a clear PASS/FAIL verdict and supporting data.

## Constraints

- All queries are read-only.
- Never approve an application that violates policy rules.
- Always cite the specific rule number when rejecting.
```

关键差异：
- 角色从"数据库助手"变为"审核 Agent"
- Workflow 加入了"Check against rules"步骤
- Constraints 加入了业务规则约束

---

## 常见错误

| 错误 | 后果 | 修正 |
|---|---|---|
| 把 Schema 放进 System Prompt | prompt 膨胀，token 浪费 | Schema 放 Skill，prompt 只放工作流 |
| 忘记写 Reflect 步骤 | 0 行结果时模型直接放弃 | 明确要求"re-read Skill and try a different query" |
| 忘记写 "ALWAYS read Skill" | 模型猜测列名和类型 | 将此指令加粗放在 Database 段之后 |
| 不写 Constraints | 模型可能尝试 INSERT/UPDATE | 明确说明只能 SELECT |
| 不指定回答语言 | 模型可能用英文回答中文问题 | 写明 "Answer in the user's language" |

---

## 小结

| 要点 | 说明 |
|---|---|
| System Prompt = 操作手册 | 定义工作流和约束，不存表结构 |
| "ALWAYS read Skill" 是最关键指令 | 缺少它模型会跳过 Skill 直接猜测 |
| Reflect 步骤防止"轻言放弃" | 0 行结果时先反思查询是否正确 |
| 不同业务场景需定制 Workflow | 审核、分析、检索各有不同步骤 |
| 保持精简 | 几十行即可，长 prompt ≠ 好 prompt |

→ 下一章：[第 4 章 · Agent 配置参考](./04-agent-config.md)
