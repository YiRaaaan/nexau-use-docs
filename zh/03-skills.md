# 第 3 章 · 用 Skills 注入领域知识

> **目标**：把数据库的"潜规则"——列名怪癖、TEXT 当数字、表怎么 join——写成 **Skills**，喂给模型。
>
> **本章结束时**：第 2 章末尾那几个失败的问题，全部能正确回答。智能体不再瞎猜列名，不再写错排序。
>
> **本章学的最重要的事**：**Skill 是 NexAU 让模型"学习领域知识"的标准机制**。它就是一个文件夹 + 一个 `SKILL.md`，跟 Claude Skills 完全兼容。

## 第 2 章的痛点回顾

第 2 章末尾的几个问题，模型都答错了：

| 问题 | 模型为什么会错 |
|---|---|
| "海淀区注册资本最高的 3 家企业" | 不知道 `register_capital` 是 **TEXT**，要 `CAST` 才能数字排序 |
| "专精特新小巨人企业有几家" | 不知道有 `zhuanjingtexin_level` 这一列，靠 `SELECT *` 摸黑试 |
| "AI 产业链上游有哪些企业" | 不知道要 join `industry_enterprise` 和 `industry`，不知道 `chain_position='up'` 表示上游 |

这些都不是 **工具问题**——`execute_sql` 已经够好了。这是 **知识问题**：模型不了解这个数据库的"潜规则"。

一个朴素的想法：**全塞进 system prompt**。但有 7 张表，每张表都有十几列、几个常用值、几个坑点（gotcha）——全塞进去 system prompt 就会膨胀到几千行，每次对话都要浪费几千 tokens（token 是大模型处理文本的最小单位，中文大致一个汉字一个 token）在"用户问的可能根本用不到的表"上面。

更好的做法：**把每张表的知识打包成一个 Skill，让模型按需读取**。

---

## 什么是 Skill

Skill 是一个 **文件夹**，里面至少有一个 `SKILL.md`，结构如下：

```
skills/
└── enterprise_basic/
    └── SKILL.md
```

`SKILL.md` 的开头是一段 YAML frontmatter（frontmatter 就是文件最前面用 `---` 包起来的元数据块，Markdown 圈的常见约定），剩下是 Markdown 正文：

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

| 字段 | 谁会读 | 作用 |
|---|---|---|
| `name` | 框架 | Skill 的唯一标识 |
| `description` | **LLM**（永远在 context 里） | 模型靠这一句话决定"我现在该不该读这个 skill" |
| 正文 | **LLM**（按需读取） | 真正的领域知识 |

所以 `description` 是**路由提示**（决定模型把当前问题"派"给哪个 Skill）——它要回答"什么时候用我"。正文是**真正的知识**——它要在被读到时尽可能完整。

> **跟 Claude Skills 兼容**：NexAU 的 Skill 格式直接复用 Claude Skills 的 schema。你在 Claude 里写的 Skill 可以直接拖进 NexAU。

---

## 写第一个 Skill：`enterprise_basic`

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

完整列表见 `enterprise_data_agent/skills/enterprise_basic/SKILL.md`（仓库里有 30+ 列）。

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

> 真实仓库的 `enterprise_data_agent/skills/enterprise_basic/SKILL.md` 比上面更详细一些
> （所有 30+ 列、更多 example）。可以直接复制过来用。

**注意三件事**：

1. **`description` 写得很具体**：列了几种典型问题（"Where is X registered?" / "How many small enterprises in 海淀区?"）。模型靠这些关键词决定"用户的问题是不是该读这个 Skill"。**description 含糊 = 模型路由错**。

2. **Schema 表写了类型 + 最关键的 gotcha**：`register_capital` 是 TEXT 这件事，是这张表最容易踩坑的点，所以紧贴在表里写出来，再到 Gotchas 章节强调一遍。

3. **Example queries 放完整 SQL**：模型读 Skill 不只是为了"知道有这一列"，而是为了"看看长得对的 SQL 应该是什么样"。范例就是 few-shot（给模型几个示范，让它照葫芦画瓢）。

---

## 写一个"反向路由"Skill：`users`

不是每个 Skill 都是"鼓励使用"，有些是"劝退使用"。`users` 表特别容易跟 `enterprise_*` 混淆——用户问"我们有几个用户"九成是问企业，但模型可能误以为是问平台账号。

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

注意 `description` 里两个关键词：

- **`ONLY when ... explicitly asks about platform users`** —— 给模型一个明确的门槛
- **`Most natural-language questions about "用户" actually mean enterprises ... confirm with the user if ambiguous`** —— 这是给模型的**消歧策略**

这就是反向路由：用 description 主动**劝退**模型，避免它误用这张表。

---

## 把剩下的 5 个 Skill 写完

照同样的格式给剩下 5 张表各写一个 Skill：

```
skills/
├── enterprise_basic/SKILL.md       ✓ 已写
├── enterprise_contact/SKILL.md     # 联系方式（管理人/电话/邮箱，全部脱敏）
├── enterprise_financing/SKILL.md   # 融资 + 上市状态
├── enterprise_product/SKILL.md     # 产品 + 知识产权
├── industry/SKILL.md               # 行业链节点（树形：chain_id/parent_id/path/depth/chain_position）
├── industry_enterprise/SKILL.md    # ↑ 跟 enterprise_basic 的 join 表
└── users/SKILL.md                  ✓ 已写
```

**懒人方案**：直接把 `enterprise_data_agent/skills/` 里的 7 个 SKILL.md 复制到你的项目里。它们就是按本章的方法论写的。

每张表的 Skill 都要回答这三个问题：

1. **什么时候用我**（`description` + "When to use"）
2. **我的列长什么样**（Schema 表）
3. **正确的 SQL 长什么样**（Example queries + Gotchas）

特别提一下 `industry` + `industry_enterprise` 这一对：它们一起构成"产业链树"。`industry` 是节点本身（带 `chain_id` / `parent_id` / `depth` / `chain_position`），`industry_enterprise` 是 enterprise 到节点的多对多映射。**用户问"AI 产业链上游有哪些企业"的时候，模型必须读这两个 Skill 才能写对 SQL**——而它会读，正是因为这两个 Skill 的 `description` 都精准命中"chain"/"上游下游"这些关键词。

---

## 在 `agent.yaml` 里注册 Skills

在第 2 章的 `agent.yaml` 末尾加一个 `skills:` 块：

```yaml
type: agent
name: enterprise_data_agent
# ... 前面的 llm_config / tools 都不变 ...

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

每一项是**指向 Skill 文件夹的相对路径**（不是 `SKILL.md` 文件本身）。框架启动时会扫描每个文件夹的 `SKILL.md`，把 frontmatter 里的 `name`/`description` 注册为可用 Skill，正文按需加载。

> **背后做了什么**：所有 Skill 的 `description` 在智能体启动时就拼到 system prompt 里（约 7 行），告诉模型"你有这些 Skill 可用"。**正文不会进 context**——只有当模型决定调用 `read_skill` 工具去读某个 Skill 的时候，正文才被注入。这就是按需加载。

> **`read_skill` 是哪儿来的?** 这是一个**框架自动注入的内置工具**，你的 `agent.yaml` 里看不到也不用写——只要 `skills:` 段非空，NexAU 在启动时就会自动把 `read_skill(name: str)` 加到智能体的工具列表里，函数体里做的就是"打开对应文件夹下的 SKILL.md，读完内容塞进对话"。所以模型一启动就有这个工具，只是它来自 NexAU 自己的代码，不是你写的。后面第 4 章你会看到另一类内置工具（`run_shell_command` / `write_todos` 之类），那些**需要你在 `tools:` 里显式声明**才能用——`read_skill` 是唯一一个隐式注入的，因为它跟 Skills 系统是一体的。

---

## 重写 system prompt

第 1、2 章的 system prompt 只是简短地告诉模型"有 7 张表"。现在我们把它**重写一遍**——一方面把 7 张表的名字明确列出来，另一方面强调"写查询前必须先读对应的 Skill"。详细的 schema、列类型、坑点不再进 prompt，全部留给 Skill 按需加载。

把 `system_prompt.md` 改成大致这个样子：

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

注意第 2 步——`**ALWAYS read the relevant Skill before writing a query**` 这一句是关键。没有这一句，模型经常会"觉得自己记得"列名，结果记错。明确写出来之后，模型每次都会先 `read_skill`。

---

## 跑起来，测之前坏掉的问题

```bash
uv run enterprise_data_agent/start.py "海淀区注册资本最高的 3 家企业是？"
```

这一次模型应该：

1. 看到问题里的 "海淀区"、"注册资本"、"企业"，决定读 `enterprise_basic` Skill
2. 在 Skill 的 Gotchas 里看到 `register_capital` 是 **TEXT**
3. 写出 `ORDER BY CAST(register_capital AS REAL) DESC LIMIT 3`
4. 拿到结果

```sql
SELECT enterprise_name,
       CAST(register_capital AS REAL) AS capital_wan
FROM enterprise_basic
WHERE register_district = '海淀区'
ORDER BY capital_wan DESC
LIMIT 3;
```

再试两个：

```bash
uv run enterprise_data_agent/start.py "专精特新小巨人企业有几家？"
```

模型读 `enterprise_basic` Skill，发现 `zhuanjingtexin_level` 这一列，**一次写对**：

```sql
SELECT COUNT(*) FROM enterprise_basic
WHERE zhuanjingtexin_level = '专精特新"小巨人"企业';
```

```bash
uv run enterprise_data_agent/start.py "AI 产业链上游有哪些企业？"
```

模型读 `industry` Skill，发现 `chain_position` 字段；读 `industry_enterprise` Skill，发现 join 模式；写出：

```sql
SELECT b.enterprise_name, i.name AS chain_node
FROM industry i
JOIN industry_enterprise ie ON ie.industry_id = i.id
JOIN enterprise_basic b      ON b.credit_code = ie.credit_code
WHERE i.chain_id = (SELECT id FROM industry WHERE name LIKE '%人工智能%' AND depth = 0)
  AND i.chain_position = 'up';
```

第 2 章这三个问题全部失败，第 3 章全部成功——**而 `agent.yaml` 只多了 7 行，`bindings.py` 一个字没改**。

---

## 你刚才学到了什么

| 概念 | 你看到的 |
|---|---|
| **Skill = 文件夹 + SKILL.md** | 跟 Claude Skills 完全兼容 |
| **frontmatter `description` 是路由** | 模型靠它决定"现在要不要读" |
| **正文是按需加载的** | 不在 context 里浪费 tokens |
| **反向路由** | `users` Skill 的 description 主动劝退 |
| **Gotchas 章节** | 把"潜规则"写成模型读得到的形式 |
| **system prompt 应当变薄** | 表清单/列名搬进 Skill，prompt 只留工作流 |

**渐进增强检查表**：

| | 第 1 章 | 第 2 章 | 第 3 章 |
|---|---|---|---|
| `agent.yaml` | ~15 行 | +`tools` 改写 | +`skills` 7 行 |
| `bindings.py` | 不存在 | 100 行 | **未改动** |
| `tools/*.tool.yaml` | 不存在 | 1 个 | **未改动** |
| `skills/*/SKILL.md` | 不存在 | 不存在 | 7 个 |
| `system_prompt.md` Workflow | 4 步 | 5 步（强调结构化返回 + reflect） | 6 步（强调读 Skill） |

---

## 局限

让模型回答一个跨多张表的复杂问题：

> "找出海淀区所有专精特新小巨人企业，列出它们的主营产品、最近一轮融资金额，并按融资金额降序排列。"

模型现在会：

1. 读 `enterprise_basic` Skill ✓
2. 读 `enterprise_product` Skill ✓
3. 读 `enterprise_financing` Skill ✓
4. 然后**直接写一个三表 join**——经常会忘记某个 WHERE 条件，或者把 join key 写错

问题不是知识不够，而是 **多步任务没有规划**。模型需要一个"草稿本"把任务拆成一步步。

NexAU 的内置工具 `write_todos` 就是干这个的。第 4 章我们会：

- 介绍 NexAU 自带的几类内置工具（文件、搜索、shell、规划）
- 重点讲 `write_todos`，把它装到我们的 agent 里
- 让 system prompt 在多表问题里**强制规划**

→ **第 4 章 · 高级内置工具教学**
