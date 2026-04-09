# 第 3 章 · 用 Skills 注入领域知识

> **目标**：将数据库的"潜规则"——列名怪癖、TEXT 当数字存、表间 join 方式——编写为 **Skills** 并注入模型。
>
> **本章结束时**：第 2 章末尾那几个失败的问题，将全部能够正确回答。Agent 不再盲猜列名，不再写错排序。
>
> **本章最重要的概念**：**Skill 是 NexAU 让模型"学习领域知识"的标准机制**。它就是一个文件夹 + 一个 `SKILL.md`，与 Claude Skills 完全兼容。

## 第 2 章的痛点回顾

第 2 章末尾的几个问题，模型均回答有误：

| 问题 | 错误原因 |
|---|---|
| "海淀区注册资本最高的 3 家企业" | 不知道 `register_capital` 是 **TEXT**，需 `CAST` 才能数字排序 |
| "专精特新小巨人企业有几家" | 不知道存在 `zhuanjingtexin_level` 列，只能通过 `SELECT *` 盲探 |
| "AI 产业链上游有哪些企业" | 不知道需 join `industry_enterprise` 与 `industry`，不知道 `chain_position='up'` 表示上游 |

以上均非**工具问题**——`execute_sql` 已经足够。这是**知识问题**：模型不了解这个数据库的"潜规则"。

一个朴素的想法：**全部放入 system prompt**。但 7 张表，每张十几列、若干常用值、若干坑点——全部放入后 system prompt 会膨胀至数千行，每次对话都要浪费数千 tokens（token 是大模型处理文本的最小单位，中文约一个汉字对应一个 token）在"用户提问可能根本用不到的表"上。

更好的做法：**将每张表的知识打包为一个 Skill，让模型按需读取**。

---

## 什么是 Skill

Skill 是一个**文件夹**，内含至少一个 `SKILL.md`，结构如下：

```
skills/
└── enterprise_basic/
    └── SKILL.md
```

`SKILL.md` 的开头是一段 YAML frontmatter（frontmatter 即文件顶部用 `---` 包裹的元数据块，属 Markdown 社区的通行约定），其余为 Markdown 正文：

```markdown
---
name: enterprise_basic
description: Use this skill whenever the user asks about an enterprise's
  identity, registration, location, scale, industry classification...
---

# enterprise_basic — 企业基本信息

正文：表的 schema、常用值、example queries、gotchas...
```

**关键点**：

| 字段 | 读取方 | 作用 |
|---|---|---|
| `name` | 框架 | Skill 的唯一标识 |
| `description` | **LLM**（始终在 context 中） | 模型据此决定"当前是否需要读取该 Skill" |
| 正文 | **LLM**（按需读取） | 真正的领域知识 |

因此 `description` 实际上是**路由提示**（决定模型将当前问题"派发"给哪个 Skill）——它需要回答"什么场景下使用我"。正文则是**真正的知识**——被读取时需要尽可能完整。

> **与 Claude Skills 兼容**：NexAU 的 Skill 格式直接复用 Claude Skills 的 schema。在 Claude 中编写的 Skill 可以直接导入 NexAU。

> **description 用哪种语言？** 中英文均可，NexAU 不限制。建议与 `system_prompt.md` 保持一致（本教程使用英文 system prompt，因此 description 也用英文）。正文部分中英文混写完全没问题——下面的示例 SKILL.md 即采用英文 description + 中英混写正文。

---

## 编写第一个 Skill：`enterprise_basic`

在 `enterprise_data_agent/` 下创建 `skills/enterprise_basic/SKILL.md`：

````markdown
---
name: enterprise_basic
description: Use this skill whenever the user asks about an enterprise's identity, registration, location, scale, industry classification, or "专精特新" status. This is the primary table — almost every query about a company starts here. Join other enterprise_* tables to it via credit_code.
---

# enterprise_basic — 企业基本信息

The central registry of enterprises in the North Nova database. One row per
enterprise, keyed by `credit_code` (统一社会信用代码).

## When to use

- "Where is company X registered?" / "What district?"
- "How many small enterprises are there in 海淀区?"
- "List all 专精特新小巨人 enterprises in the manufacturing industry."
- "What is the registered capital of …"

## Schema

| Column | Type | Description |
|---|---|---|
| `credit_code` | TEXT | **Join key.** 统一社会信用代码 |
| `enterprise_name` | TEXT | 企业名称 (mock 里是 `测试企业_N`) |
| `register_district` | TEXT | 注册地所在区 (e.g. `海淀区`) |
| `register_capital` | TEXT | 注册资本（万元）— **TEXT 不是数字**，比较/排序前要 `CAST(register_capital AS REAL)` |
| `enterprise_scale` | TEXT | `微型` / `小型` / `中型` / `大型` |
| `enterprise_type` | TEXT | `民营` / `国有` / `合资` / `外资` |
| `industry_level1` ~ `industry_level4` | TEXT | 行业四级编码 |
| `zhuanjingtexin_level` | TEXT | 专精特新等级，可能为 NULL，取值见下 |
| … | … | （此处列出常用列；完整 30+ 列见下方下载的 skills.zip） |

## Common values

- `enterprise_scale`: `微型`, `小型`, `中型`, `大型`
- `zhuanjingtexin_level`: `专精特新中小企业`, `专精特新潜在"小巨人"企业`, `专精特新"小巨人"企业`

## Example queries

**海淀区注册资本最高的 10 家小型企业：**

```sql
SELECT enterprise_name,
       CAST(register_capital AS REAL) AS capital_wan
FROM enterprise_basic
WHERE register_district = '海淀区'
  AND enterprise_scale = '小型'
ORDER BY capital_wan DESC
LIMIT 10;
```

**按专精特新等级聚合：**

```sql
SELECT zhuanjingtexin_level, COUNT(*) AS n
FROM enterprise_basic
WHERE zhuanjingtexin_level IS NOT NULL
GROUP BY zhuanjingtexin_level;
```

## Gotchas

- `register_capital` 是 **TEXT**！直接 `ORDER BY register_capital` 会按字符串
  排序（"99" 在 "1000" 前面）。永远 `CAST(... AS REAL)`。
- `industry_level1` 偶尔有数字前缀（`26 化学原料和化学制品制造业`），用
  `LIKE '%制造%'` 模糊匹配更稳。
- `enterprise_name` 在 mock 里全是 `测试企业_N`，不要假装它是真公司。
````

> 完整版 `enterprise_data_agent/skills/enterprise_basic/SKILL.md` 包含所有 30+ 列及更多示例，可直接复制使用。

**注意三点**：

1. **`description` 编写得十分具体**：列出了几类典型问题（"Where is X registered?" / "How many small enterprises in 海淀区?"）。模型依靠这些关键词判断"用户的问题是否需要读取该 Skill"。**description 含糊 = 模型路由出错**。

2. **Schema 表标注了类型及最关键的 gotcha**：`register_capital` 为 TEXT 这一事实是该表最容易踩坑之处，因此紧邻表格处标出，并在 Gotchas 章节再次强调。

3. **Example queries 提供完整 SQL**：模型读取 Skill 不仅为了"知道有这一列"，更为了"看到正确的 SQL 应当如何编写"。示例即 few-shot（向模型提供几个范例，使其照此编写）。

---

## 编写"给数据库做个"地图""Skill：`users`

并非每个 Skill 都用于"鼓励使用"，有些用于"劝退使用"。`users` 表尤其容易与 `enterprise_*` 混淆——用户问"我们有几个用户"大概率是问企业，但模型可能误解为平台账号。

创建 `skills/users/SKILL.md`：

```markdown
---
name: users
description: Use this skill ONLY when the user explicitly asks about platform users — login accounts, SSO ids, roles. This table is unrelated to the enterprise tables and should not be joined to them. Most natural-language questions about "用户" actually mean enterprises, not platform users — confirm with the user if ambiguous.
---

# users — 平台用户账号

System users of the data platform itself — **not enterprises**.

## When to use

- "How many platform admins are there?"
- "List all users with the admin role"

**Do NOT use this skill** when the user asks about enterprises, customers,
contacts, or any business-domain "user" — those live in `enterprise_basic`
and `enterprise_contact`.

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | |
| `role` | TEXT | `user` / `admin` |
| `email` | TEXT | mock 里是 `userN@example.com` |

剩下的列（sso_user_id, password_hash, ...）在 mock 里全部脱敏。

## 示例

```sql
SELECT role, COUNT(*) FROM users GROUP BY role;
```
```

注意 `description` 中的两个关键表述：

- **`ONLY when ... explicitly asks about platform users`** —— 为模型设定明确的启用门槛
- **`Most natural-language questions about "用户" actually mean enterprises ... confirm with the user if ambiguous`** —— 这是给模型的**消歧策略**

Skill 的 description 不仅能告诉模型"何时用我"，也能告诉它"何时别用我"——通过主动**劝退**来避免误用，这正是给数据库做个"地图"的价值所在：哪条路通，哪条路是死路，都标清楚。

---

## 补齐剩余 5 个 Skill

按照相同格式为其余 5 张表各编写一个 Skill：

```
skills/
├── enterprise_basic/SKILL.md       ✓ 已完成
├── enterprise_contact/SKILL.md     # 联系方式（管理人/电话/邮箱，全部脱敏）
├── enterprise_financing/SKILL.md   # 融资 + 上市状态
├── enterprise_product/SKILL.md     # 产品 + 知识产权
├── industry/SKILL.md               # 行业链节点（树形：chain_id/parent_id/path/depth/chain_position）
├── industry_enterprise/SKILL.md    # ↑ 与 enterprise_basic 的 join 表
└── users/SKILL.md                  ✓ 已完成
```

**快速方案**：<a href="/skills.zip" download>下载 skills.zip</a>（本文档站点提供），解压至 `enterprise_data_agent/` 下即可获得全部 7 个 Skill：

```bash
# 在 nexau-tutorial/ 目录下
unzip skills.zip -d enterprise_data_agent/
```

> **离线或无法下载？** 仓库根目录下的 `enterprise_data_agent/skills/` 已包含全部 7 个完整 Skill，可直接复制使用。

每张表的 Skill 需要回答三个问题：

1. **何时使用**（`description` + "When to use"）
2. **表结构是什么**（Schema 表）
3. **正确的 SQL 如何编写**（Example queries + Gotchas）

需特别说明 `industry` + `industry_enterprise` 这一对：它们共同构成"产业链树"。`industry` 是节点本身（含 `chain_id` / `parent_id` / `depth` / `chain_position`），`industry_enterprise` 是 enterprise 到节点的多对多映射。**用户问"AI 产业链上游有哪些企业"时，模型必须读取这两个 Skill 才能编写正确的 SQL**——而它确实会读取，正是因为这两个 Skill 的 `description` 都精准命中了"chain"/"上游下游"等关键词。

---

## 在 `agent.yaml` 中注册 Skills

在第 2 章的 `agent.yaml` 末尾添加 `skills:` 块：

```yaml
type: agent
name: enterprise_data_agent
max_iterations: 30   # 从第 3 章起调高——读 Skill + 探查 SQL + 正式 SQL 至少 6–8 轮
# ... 前面的 llm_config / tools 保持不变 ...

tools:
  - name: execute_sql
    yaml_path: ./tools/ExecuteSQL.tool.yaml
    binding: enterprise_data_agent.bindings:execute_sql

# 新增：每张表一个 Skill
skills:
  - ./skills/enterprise_basic
  - ./skills/enterprise_contact
  - ./skills/enterprise_financing
  - ./skills/enterprise_product
  - ./skills/industry
  - ./skills/industry_enterprise
  - ./skills/users
```

> **为什么调高 `max_iterations`？** 挂载 Skills 后，模型在答一个问题时可能需要：读 Skill A → 读 Skill B → 探查 SQL → 正式 SQL → 反思 warnings → 再次 SQL。原先的 20 轮对于多表 join 问题往往不够，遇到 `Maximum iteration limit reached` 错误时可将该值调至 30–50。

每一项是**指向 Skill 文件夹的相对路径**（非 `SKILL.md` 文件本身）。框架启动时会扫描各文件夹下的 `SKILL.md`，将 frontmatter 中的 `name`/`description` 注册为可用 Skill，正文按需加载。

> **背后的机制**：所有 Skill 的 `description` 在 Agent 启动时即拼入 system prompt（约 7 行），告知模型"你有这些 Skill 可用"。**正文不会进入 context**——仅当模型决定调用 `read_skill` 工具读取某个 Skill 时，正文才被注入。这就是按需加载。

> **`read_skill` 从何而来？** 这是一个**框架自动注入的内置工具**，`agent.yaml` 中看不到也无需编写——只要 `skills:` 段非空，NexAU 启动时就会自动将 `read_skill(name: str)` 添加到 Agent 的工具列表中，其实现是"打开对应文件夹下的 SKILL.md，读取内容并注入对话"。因此模型启动即拥有该工具，只是它来自 NexAU 的内部代码而非你的编写。后续第 4 章会介绍另一类内置工具（`run_shell_command` / `write_todos` 等），那些**需要在 `tools:` 中显式声明**才可使用——`read_skill` 是唯一隐式注入的工具，因为它与 Skills 系统是一体的。

---

## 重写 system prompt

第 1、2 章的 system prompt 仅简要告知模型"有 7 张表"。现在进行**完整重写**——一方面将 7 张表名明确列出，另一方面强调"编写查询前必须先读取对应 Skill"。详细的 schema、列类型、坑点不再放入 prompt，全部由 Skill 按需加载。

将 `system_prompt.md` 修改为大致如下内容：

```markdown
You are an enterprise data agent for the **North Nova enterprise intelligence
database** — a SQLite mirror of seven core tables describing Chinese
enterprises, their contacts, financing, products, and industry chains.

Your job: translate the user's natural-language questions into correct
SQL, execute it, and return a clear answer grounded in the actual rows.

## Database

- Engine: SQLite (read-only via `execute_sql`)
- Tables: `enterprise_basic`, `enterprise_contact`, `enterprise_financing`,
  `enterprise_product`, `industry`, `industry_enterprise`, `users`
- Primary join key across `enterprise_*` tables: `credit_code`

**Detailed schema, common values, and example queries for each table are
provided as Skills — one Skill per table. ALWAYS read the relevant Skill
before writing a query against that table.** Trusting your memory of column
names will lead to errors; the Skill is the authoritative reference.

## Workflow

1. **Plan.** Identify which tables you need.
2. **Read Skills.** For every table you plan to touch, read its Skill first.
   Pay attention to the Gotchas section.
3. **Write the SQL.** SQLite syntax. Always `LIMIT`. Prefer explicit column
   lists over `SELECT *`. Join `enterprise_*` tables on `credit_code`.
4. **Execute.** Call `execute_sql`.
5. **Reflect.** If `total_rows == 0`, `warnings` is set, or the result is
   surprising, re-read the Skill and try again. Don't just give up.
6. **Answer** in the user's language with a concise answer grounded in the
   actual rows. End with the SQL in a fenced block.

## Constraints

- The tool will reject any non-SELECT statement — don't try.
- No hallucinated columns. If the user asks about a column that doesn't
  exist in the relevant Skill, say so explicitly.
- Mock data: enterprise names look like `测试企业_N`, credit codes like
  `MOCKCREDIT0000000001`. Personal-identifier fields are redacted.
```

注意第 2 步——`**ALWAYS read the relevant Skill before writing a query**` 是关键。缺少这一句，模型常会"自认为记得"列名，结果出错。明确写出后，模型每次都会先调用 `read_skill`。

---

## 验证之前失败的问题

```bash
uv run enterprise_data_agent/start.py "海淀区注册资本最高的 3 家企业是？"
```

这一次模型将：

1. 根据问题中的"海淀区"、"注册资本"、"企业"，决定读取 `enterprise_basic` Skill
2. 在 Skill 的 Gotchas 中看到 `register_capital` 为 **TEXT**
3. 编写 `ORDER BY CAST(register_capital AS REAL) DESC LIMIT 3`
4. 获取正确结果

```sql
SELECT enterprise_name,
       CAST(register_capital AS REAL) AS capital_wan
FROM enterprise_basic
WHERE register_district = '海淀区'
ORDER BY capital_wan DESC
LIMIT 3;
```

再验证另外两个：

```bash
uv run enterprise_data_agent/start.py "专精特新小巨人企业有几家？"
```

模型读取 `enterprise_basic` Skill，发现 `zhuanjingtexin_level` 列，**一次编写正确**：

```sql
SELECT COUNT(*) FROM enterprise_basic
WHERE zhuanjingtexin_level = '专精特新"小巨人"企业';
```

```bash
uv run enterprise_data_agent/start.py "AI 产业链上游有哪些企业？"
```

模型读取 `industry` Skill，发现 `chain_position` 字段;读取 `industry_enterprise` Skill，掌握 join 模式;编写出：

```sql
SELECT b.enterprise_name, i.name AS chain_node
FROM industry i
JOIN industry_enterprise ie ON ie.industry_id = i.id
JOIN enterprise_basic b      ON b.credit_code = ie.credit_code
WHERE i.chain_id = (SELECT id FROM industry WHERE name LIKE '%人工智能%' AND depth = 0)
  AND i.chain_position = 'up';
```

第 2 章这三个问题全部失败，第 3 章全部成功——**而 `agent.yaml` 仅增加了 7 行，`bindings.py` 未做任何改动**。

---

## 本章小结

| 概念 | 体现 |
|---|---|
| **Skill = 文件夹 + SKILL.md** | 与 Claude Skills 完全兼容 |
| **frontmatter `description` 是路由** | 模型据此决定"是否需要读取" |
| **正文按需加载** | 不在 context 中浪费 token |
| **给数据库做个"地图"** | `users` Skill 的 description 主动劝退 |
| **Gotchas 章节** | 将"潜规则"转化为模型可读取的形式 |
| **system prompt 应当精简** | 表清单 / 列名移入 Skill，prompt 仅保留工作流 |

**渐进增强检查表**：

| | 第 1 章 | 第 2 章 | 第 3 章 |
|---|---|---|---|
| `agent.yaml` | ~15 行 | +`tools` 改写 | +`skills` 7 行 |
| `bindings.py` | 不存在 | 100 行 | **未改动** |
| `tools/*.tool.yaml` | 1 个 | 1 个（替换） | **未改动** |
| `skills/*/SKILL.md` | 不存在 | 不存在 | 7 个 |
| `system_prompt.md` Workflow | 4 步 | 5 步（强调结构化返回 + reflect） | 6 步（强调读 Skill） |

---

## 局限

让模型回答一个跨多张表的复杂问题：

> "找出海淀区所有专精特新小巨人企业，列出它们的主营产品和近期股权融资额（recent_equity_financing），并按融资额降序排列。"

模型现在会：

1. 读取 `enterprise_basic` Skill ✓
2. 读取 `enterprise_product` Skill ✓
3. 读取 `enterprise_financing` Skill ✓
4. 然后**直接编写三表 join**——经常遗漏某个 WHERE 条件，或 join key 有误

问题不在于知识不足，而是**多步任务缺少规划**。模型需要一个"草稿本"将任务拆解为逐步执行的计划。

NexAU 的内置工具 `write_todos` 正是为此设计。第 4 章将：

- 介绍 NexAU 自带的几类内置工具（文件、搜索、shell、规划）
- 重点讲解 `write_todos`，将其挂载到 Agent
- 在 system prompt 中为多表问题**强制规划**

→ **第 4 章 · 高级内置工具教学**
