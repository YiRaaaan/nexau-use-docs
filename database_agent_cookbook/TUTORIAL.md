# 如何为数据库场景编写 Skill：以企业问答 Agent 为例

> 本文通过一个 7 张表的企业数据库，拆解如何编写 SKILL.md 来提升数据库 Agent 的问答准确率。核心观点：Agent 答错不是因为模型不会写 SQL，而是不了解你的数据库——Skill 就是把你的领域知识传递给模型的方式。

## 目录

- [背景：企业数据库概览](#背景企业数据库概览)
- [要点 1：System Prompt 只管工作流](#要点-1system-prompt-只管工作流)
- [要点 2：Skill 的两层结构——路由与知识分离](#要点-2skill-的两层结构路由与知识分离)
- [要点 3：类型陷阱——准确率的第一杀手](#要点-3类型陷阱准确率的第一杀手)
- [要点 4：业务规则——只有你知道的知识](#要点-4业务规则只有你知道的知识)
- [要点 5：用表格代替散文](#要点-5用表格代替散文)
- [要点 6：跨表查询——引导模型正确 Join](#要点-6跨表查询引导模型正确-join)
- [要点 7：description 是路由标签，不是说明文档](#要点-7description-是路由标签不是说明文档)
- [要点 8：测试驱动——每次答错就改一条 Skill](#要点-8测试驱动每次答错就改一条-skill)
- [完整示例：enterprise_basic 的 SKILL.md](#完整示例enterprise_basic-的-skillmd)
- [附：自动生成 Skill 草稿](#附自动生成-skill-草稿)
- [动手实践：构建你自己的数据库 Agent](#动手实践构建你自己的数据库-agent)

---

## 背景：企业数据库概览

本文使用一个**企业智能数据库**，包含 7 张表、50 家企业：

| 表名 | 说明 | 关联 |
|------|------|------|
| `enterprise_basic` | 企业基本信息（注册、行业、专精特新等，37 列） | 主表，其他 enterprise_* 表通过 `credit_code` 关联 |
| `enterprise_contact` | 联系人（法人、总经理、联系人） | `credit_code` → `enterprise_basic` |
| `enterprise_financing` | 融资与上市（贷款、估值、上市状态） | `credit_code` → `enterprise_basic` |
| `enterprise_product` | 产品与知识产权（产品营收、专利） | `credit_code` → `enterprise_basic` |
| `industry` | 行业链节点（树结构：上游/中游/下游） | 被 `industry_enterprise` 引用 |
| `industry_enterprise` | 企业 ↔ 行业链映射 | `industry_id` → `industry`，`credit_code` → `enterprise_basic` |
| `users` | 平台用户账号 | **独立表，与企业无关** |

这个数据库和真实场景一样有"坑"：`register_capital`（注册资本）是 TEXT 类型，`zhuanjingtexin_level`（专精特新等级）有隐式高低之分，`users` 表容易被误用。这些坑就是 Skill 要解决的问题。

---

## 要点 1：System Prompt 只管工作流

大多数人写 Agent 会把表结构、业务规则全塞进 System Prompt。这个项目把内容分成了两层：

| 层级 | 文件 | 职责 | 变更频率 |
|------|------|------|---------|
| 工作流层 | `system_prompt.md` | 角色定义、处理流程、全局约束 | 低 |
| 知识层 | `skills/表名/SKILL.md` | 每张表的 Schema、枚举值、示例 SQL、Gotchas | 中 |

**为什么这样做？**

```
❌ 反面教材：所有内容塞进 System Prompt
   → 7 张表的知识写进去就 2000+ 行
   → 改一张表的枚举值要翻整个 prompt
   → token 浪费严重（每次对话都加载全部表知识）

✅ 本项目的做法：System Prompt 只放工作流，表知识放 Skill
   → System Prompt 不到 40 行，告诉 Agent "怎么干活"
   → 每张表的 Skill 独立维护，改一张不影响其他
   → Skill 按需加载，模型只读取需要的表
```

System Prompt 回答的是"你是谁"和"你怎么干活"，不回答"你知道什么"：

```markdown
## Workflow

1. Plan. — 识别需要哪些表
2. Read Skills. — 读取相关表的 Skill
3. Write the SQL. — SQLite 语法，始终 LIMIT
4. Execute. — 调用 execute_sql
5. Reflect. — 0 行或有 warning？重新检查 Skill
6. Answer — 用用户的语言回答，附上 SQL
```

唯一写进 System Prompt 的"知识"是**全局 Gotchas**——那些跨表的、每次都需要注意的陷阱：

```markdown
### Key gotchas (always visible)

- enterprise_basic.register_capital is TEXT — use CAST(register_capital AS REAL)
- enterprise_product.daily_capacity is TEXT — use CAST(daily_capacity AS REAL)
- zhuanjingtexin_level values: 专精特新中小企业 < 专精特新潜在"小巨人"企业 < 专精特新"小巨人"企业
- users table = platform accounts, NOT enterprises. "用户" usually means enterprise.
```

这些 Gotchas 之所以放在 System Prompt 而不是 Skill 里，是因为它们**太重要了，不能等模型"决定读取"才看到**。

---

## 要点 2：Skill 的两层结构——路由与知识分离

每个 Skill 是一个文件夹里的 `SKILL.md`，由两部分组成：

```markdown
---
name: enterprise_basic
description: Use this skill whenever the user asks about an enterprise's
  identity, registration, location, scale, or industry classification.
---

# enterprise_basic — 企业基本信息
（正文：Schema、示例 SQL、注意事项...）
```

- **`description`（始终对模型可见）** — 告诉模型"什么时候该读取这个 Skill"。它是路由标签，不是内容摘要。
- **正文（模型决定读取时才加载）** — 告诉模型"这张表具体怎么查"。包含 Schema、Common values、Example queries、Gotchas。

这种设计的好处：7 张表的 description 加起来不到 500 token，始终可见；但每张表的完整知识（Schema + 示例 + Gotchas）可能有 200-500 行，只在需要时才加载。

---

## 要点 3：类型陷阱——准确率的第一杀手

`register_capital`（注册资本）在数据库中是 TEXT 类型。直接 `ORDER BY register_capital DESC`，"8000" 会排在 "50000" 前面——因为字母序 `"8" > "5"`。

**Skill 中需要在三个地方提示模型**，形成"三点联动"：

**① Schema 表——紧邻列名标注**：

```
| `register_capital` | TEXT | 注册资本（万元）— TEXT not numeric, use CAST(register_capital AS REAL) |
```

**② Example queries——展示正确写法**：

```sql
SELECT enterprise_name, CAST(register_capital AS REAL) AS capital_wan
FROM enterprise_basic
WHERE register_district = '海淀区'
ORDER BY capital_wan DESC LIMIT 10;
```

**③ Gotchas——解释为什么错**：

```
- register_capital is TEXT — always CAST(register_capital AS REAL).
  Direct ORDER BY gives wrong results (string sort: "8000" > "50000").
```

三处信息互相加强：Schema 让模型注意到类型，Example 提供正确模板，Gotchas 解释原因。只写一处，模型可能忽略；三处同时提示，遗漏概率大幅降低。

同理，`enterprise_product.daily_capacity` 也是 TEXT 存数字，需要同样处理。

---

## 要点 4：业务规则——只有你知道的知识

类型陷阱看 Schema 就能发现，但**业务规则只有了解业务的人才知道**。这是 Skill 最有价值的部分。

### 4.1 枚举等级

`zhuanjingtexin_level` 的值有隐含的高低之分：

```
- zhuanjingtexin_level hierarchy:
  专精特新中小企业 < 专精特新潜在"小巨人"企业 < 专精特新"小巨人"企业
  NULL = 无专精特新认定
  "小巨人企业": WHERE zhuanjingtexin_level = '专精特新"小巨人"企业'
```

不写这条，Agent 不知道"小巨人"对应的精确值——它可能写出 `WHERE zhuanjingtexin_level = '小巨人'`，查不到任何结果。

### 4.2 上市状态

`enterprise_financing.listing_status` 有 4 个值，不同的问法对应不同的过滤条件：

```
- listing_status values: 未上市, 新三板, 已上市, 拟上市
  "已上市的企业" = WHERE listing_status = '已上市'
  "有上市计划的" = WHERE listing_status IN ('拟上市', '已上市')
```

### 4.3 行业链的树结构

`industry` 表是一棵树，不是一张扁平表。不写清楚层级关系，模型不知道怎么查"AI 上游企业"：

```
- depth=0: chain root, depth=1: 上游/中游/下游, depth=2: leaf nodes
- chain_position ('up'/'mid'/'down') ONLY on depth=1 nodes
- "AI 上游企业" = join industry (chain_position='up') → industry_enterprise → enterprise_basic
```

### 4.4 容易混淆的表

`users` 是平台账号，不是企业。用户说"用户"时 99% 指的是企业：

```
- "用户"在本数据库中通常指企业（enterprise_basic），不是平台用户（users）
- 只有明确问"平台管理员"、"登录账号"时才查 users 表
```

---

## 要点 5：用表格代替散文

对比两种写 Schema 的方式：

```
❌ 散文写法：
enterprise_basic 表有 37 列，其中 credit_code 是统一社会信用代码，
用于与其他 enterprise_* 表关联。register_capital 是注册资本，
但注意它是 TEXT 类型需要 CAST。enterprise_scale 有四个取值……

✅ 表格写法：
| Column | Type | Description |
|---|---|---|
| `credit_code` | TEXT | **Join key.** 统一社会信用代码 |
| `register_capital` | TEXT | 注册资本（万元）— **TEXT**, use CAST |
| `enterprise_scale` | TEXT | One of `微型`, `小型`, `中型`, `大型` |
```

表格的好处：

1. **LLM 更容易精准定位** — 模型做表格查找比从段落中提取信息更准确
2. **减少遗漏** — 每一行都是独立条目，不会因为段落太长而"看丢了"
3. **便于维护** — 改一行不影响其他行

类似地，枚举值用 Common values 段落集中列出，而不是散落在各处：

```markdown
## Common values

- `enterprise_scale`: `微型`, `小型`, `中型`, `大型`
- `enterprise_type`: `民营`, `国有`, `合资`, `外资`
- `zhuanjingtexin_level`: `专精特新中小企业` < `专精特新潜在"小巨人"企业` < `专精特新"小巨人"企业`
```

---

## 要点 6：跨表查询——引导模型正确 Join

用户问"专精特新小巨人企业中有哪些已上市？"需要 join `enterprise_basic` 和 `enterprise_financing` 两张表。模型需要知道三件事：**用什么 key join**、**join 哪张表**、**完整的 SQL 长什么样**。

**在 description 中标注 join 关系**：

```yaml
description: >-
  Use this skill whenever the user asks about an enterprise's identity,
  registration, location, scale, or industry classification.
  Join other enterprise_* tables via credit_code.
```

**在 Schema 中标注 join key**：

```
| `credit_code` | TEXT | **Join key.** 统一社会信用代码 — shared across all enterprise_* tables. |
```

**在 Example queries 中提供 join 示例**：

```sql
-- 两表 join：专精特新小巨人 + 已上市
SELECT b.enterprise_name, f.listing_status, f.stock_code
FROM enterprise_basic b
JOIN enterprise_financing f ON b.credit_code = f.credit_code
WHERE b.zhuanjingtexin_level = '专精特新"小巨人"企业'
  AND f.listing_status = '已上市';
```

**三表 join 更需要引导**——"AI 上游有哪些企业"涉及 industry → industry_enterprise → enterprise_basic：

```sql
SELECT b.enterprise_name, i.name AS industry_node
FROM industry i
JOIN industry_enterprise ie ON ie.industry_id = i.id
JOIN enterprise_basic b ON b.credit_code = ie.credit_code
WHERE i.chain_id = 45 AND i.chain_position = 'up';
```

没有这些示例，模型很可能用错 join key 或漏掉中间表。

---

## 要点 7：description 是路由标签，不是说明文档

`description` 决定模型"是否读取这个 Skill"。它始终可见，所以每个字都要有路由价值。

**正面路由**——关键词要覆盖用户的不同说法：

```yaml
description: >-
  Use this skill whenever the user asks about an enterprise's financing —
  bank loans, equity rounds, valuation, listing status, planned listing
  location, or future financing demand. Join with enterprise_basic via credit_code.
```

**负面路由**——有些表容易被混淆，需要主动"劝退"：

```yaml
description: >-
  Use this skill ONLY when the user explicitly asks about platform users —
  login accounts, SSO ids, roles. This table is unrelated to the enterprise
  tables. Most questions about "用户" actually mean enterprises, not platform users.
```

常见反模式：

| 反模式 | 问题 | 改进 |
|--------|------|------|
| `"企业基本信息"` | 太笼统，模型不知道什么时候该用 | `"Use when user asks about registration, location, scale, industry, 专精特新 status"` |
| `"融资表"` | 纯标签，没有路由能力 | `"Use when user asks about bank loans, equity, valuation, listing status"` |
| 把 Schema 塞进 description | 浪费 token，description 始终可见 | description 只放路由提示，Schema 放正文 |

---

## 要点 8：测试驱动——每次答错就改一条 Skill

写完 Skill 后，用边界问题验证：

- TEXT 数字列的排序："注册资本最高的企业"
- 枚举值精确匹配："专精特新小巨人企业有哪些"
- 跨表查询："已上市的小巨人企业"
- 三表 join："AI 产业链上游有哪些企业"
- 负面路由："平台有多少管理员"（应走 users，不是 enterprise_basic）

**每次 Agent 答错，分析根因并更新 Skill**：

| Agent 的错误 | Skill 如何修改 |
|-------------|---------------|
| 没有读取该 Skill | description 中加入用户使用的关键词 |
| 类型处理错误 | Schema + Gotchas + Example 三处同时加提示 |
| 枚举值写错 | Common values 中加入精确值 |
| Join 写错 | Schema 标注 FK，description 加 join 说明 |
| 误用 users 表 | users 的 description 加强负面路由 |

**Skill 是活文档——每修复一个错误就加一条提示，准确率逐步提升。**

---

## 完整示例：enterprise_basic 的 SKILL.md

下面是 `enterprise_basic` 的完整 Skill，注意观察前面讲到的每个技巧是如何落地的：

````markdown
---
name: enterprise_basic
description: >-
  Use this skill whenever the user asks about an enterprise's identity,
  registration, location, scale, industry classification, or 专精特新 status.
  This is the primary table — almost every query about a company starts here.
  Join other enterprise_* tables to it via credit_code.
---

# enterprise_basic — 企业基本信息

The central registry of enterprises. One row per enterprise, keyed by `credit_code`.

## When to use

- "Where is company X registered?" / "What district?"
- "How many small enterprises are there in 海淀区?"
- "List all 专精特新小巨人 enterprises"
- "What is the registered capital of …"

For contact info go to `enterprise_contact`, for financing go to `enterprise_financing`,
for products go to `enterprise_product`.

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Internal row id |
| `credit_code` | TEXT | **Join key.** 统一社会信用代码 — shared across all enterprise_* tables |
| `enterprise_name` | TEXT | 企业名称 |
| `register_district` | TEXT | 注册地所在区 (e.g. `海淀区`, `黄浦区`, `南山区`) |
| `register_capital` | TEXT | 注册资本（万元）— **TEXT not numeric**, use `CAST(register_capital AS REAL)` |
| `enterprise_scale` | TEXT | One of `微型`, `小型`, `中型`, `大型` |
| `enterprise_type` | TEXT | One of `民营`, `国有`, `合资`, `外资` |
| `industry_level1` | TEXT | 行业一级分类 (e.g. `制造业`, `金融业`) |
| `zhuanjingtexin_level` | TEXT | 专精特新等级 — see Common values |
| ... | | (37 columns total, see full schema for details) |

## Common values

- `enterprise_scale`: `微型`, `小型`, `中型`, `大型`
- `enterprise_type`: `民营`, `国有`, `合资`, `外资`
- `zhuanjingtexin_level`: `专精特新中小企业` < `专精特新潜在"小巨人"企业` < `专精特新"小巨人"企业`

## Example queries

**Top 10 enterprises by registered capital in 海淀区:**
```sql
SELECT enterprise_name,
       CAST(register_capital AS REAL) AS capital_wan,
       enterprise_scale
FROM enterprise_basic
WHERE register_district = '海淀区'
ORDER BY capital_wan DESC LIMIT 10;
```

**Count of 专精特新 enterprises by level:**
```sql
SELECT zhuanjingtexin_level, COUNT(*) AS n
FROM enterprise_basic
WHERE zhuanjingtexin_level IS NOT NULL
GROUP BY zhuanjingtexin_level ORDER BY n DESC;
```

**Join with financing to find listed 小巨人 companies:**
```sql
SELECT b.enterprise_name, f.listing_status, f.stock_code
FROM enterprise_basic b
JOIN enterprise_financing f ON b.credit_code = f.credit_code
WHERE b.zhuanjingtexin_level = '专精特新"小巨人"企业'
  AND f.listing_status = '已上市';
```

## Gotchas

- `register_capital` is **TEXT** — cast with `CAST(register_capital AS REAL)` for sorting/comparison.
- `zhuanjingtexin_level` contains Chinese quotes — match exactly: `'专精特新"小巨人"企业'`
- `enterprise_name` in mock data looks like `测试企业_N`.
````

同时看一个**负面路由**的示例——`users` 表的 Skill：

```markdown
---
name: users
description: >-
  Use this skill ONLY when the user explicitly asks about platform users —
  login accounts, SSO ids, roles. This table is unrelated to the enterprise
  tables and should not be joined to them. Most questions about "用户" actually
  mean enterprises, not platform users — confirm with the user if ambiguous.
---

# users — 平台用户账号

System users of the data platform itself — not enterprises.

## When to use

- "How many platform admins are there?"
- "List all users with the admin role"

**Do NOT use** when the user asks about enterprises, customers, or contacts.
```

---

## 附：自动生成 Skill 草稿

7 张表手写没问题，70 张表就需要自动化了。以下脚本读取任意 SQLite，为每张表生成 SKILL.md 草稿：

- 表结构（列名、类型、主键、外键）
- TEXT 列实际存储数字的情况（自动检测）
- 枚举型列（取值较少的列自动列出）
- 外键关系（自动生成 JOIN 示例）
- 需要人工判断的地方标记 `[TODO]`

```python
import re
import sqlite3


def get_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def get_table_info(conn, table):
    rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    return [{"name": r[1], "type": r[2] or "TEXT", "pk": bool(r[5]),
             "notnull": bool(r[3]), "default": r[4]} for r in rows]


def get_foreign_keys(conn, table):
    rows = conn.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()
    return {r[3]: f"{r[2]}.{r[4]}" for r in rows}


def get_common_values(conn, table, col, limit=8):
    try:
        rows = conn.execute(
            f"SELECT [{col}], COUNT(*) AS n FROM [{table}] "
            f"WHERE [{col}] IS NOT NULL "
            f"GROUP BY [{col}] ORDER BY n DESC LIMIT ?", (limit,)
        ).fetchall()
        return [(str(r[0]), r[1]) for r in rows]
    except Exception:
        return []


def is_numeric_in_text(conn, table, col):
    try:
        sample = conn.execute(
            f"SELECT [{col}] FROM [{table}] WHERE [{col}] IS NOT NULL LIMIT 20"
        ).fetchall()
        if not sample:
            return False
        numeric_count = sum(
            1 for r in sample
            if r[0] is not None and re.match(r"^-?\d+(\.\d+)?$", str(r[0]).strip())
        )
        return numeric_count / len(sample) > 0.8
    except Exception:
        return False


def generate_skill_md(conn, table):
    columns = get_table_info(conn, table)
    fk_map = get_foreign_keys(conn, table)
    row_count = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]

    pk_cols = [c["name"] for c in columns if c["pk"]]
    pk_str = ", ".join(f"`{c}`" for c in pk_cols) if pk_cols else "(no explicit PK)"

    fk_notes = [f"`{lc}` -> `{ref}`" for lc, ref in fk_map.items()]
    fk_hint = " Join keys: " + ", ".join(fk_notes) + "." if fk_map else ""

    schema_rows = []
    for col in columns:
        parts = []
        if col["pk"]:
            parts.append("PK")
        if col["name"] in fk_map:
            parts.append(f"FK -> `{fk_map[col['name']]}`")
        desc = " | ".join(parts) if parts else ""
        schema_rows.append(f"| `{col['name']}` | {col['type']} | {desc} |")

    common_sections = []
    for col in columns:
        if col["type"].upper() != "TEXT" or col["pk"]:
            continue
        vals = get_common_values(conn, table, col["name"])
        if 2 <= len(vals) <= 10:
            val_str = ", ".join(f"`{v[0]}`" for v in vals)
            common_sections.append(f"- `{col['name']}`: {val_str}")

    gotchas = []
    for col in columns:
        if col["type"].upper() == "TEXT" and is_numeric_in_text(conn, table, col["name"]):
            gotchas.append(
                f"- `{col['name']}` is **TEXT** but stores numeric values — "
                f"use `CAST({col['name']} AS REAL)` for comparisons and sorting."
            )

    nl = "\n"
    return (
        f"---\nname: {table}\ndescription: >-\n"
        f"  Use this skill when the user asks about `{table}`.{fk_hint}\n"
        f"  [TODO: Add routing keywords]\n---\n\n"
        f"# {table}\n\nRows: **{row_count}** | PK: {pk_str}\n"
        f"\n## Schema\n\n| Column | Type | Description |\n|---|---|---|\n"
        f"{nl.join(schema_rows)}\n"
        f"\n## Common values\n\n"
        f"{nl.join(common_sections) if common_sections else '- [TODO]'}\n"
        f"\n## Gotchas\n\n"
        f"{nl.join(gotchas) if gotchas else '- [TODO]'}\n"
    )
```

**自动生成是起点，人工补充业务知识才是关键。** 脚本能发现 TEXT 存数字、枚举值、外键关系，但不知道专精特新等级的高低顺序、"用户"在本场景指企业而非平台账号——这些需要你来补充。

---

## 动手实践：构建你自己的数据库 Agent

根据以上分析，总结核心原则：

| # | 原则 | 一句话 |
|---|------|-------|
| 1 | System Prompt 只管工作流 | 告诉 Agent "怎么干活"，不告诉它"你知道什么" |
| 2 | 路由与知识分离 | description 始终可见做路由，正文按需加载放知识 |
| 3 | 三点联动治类型陷阱 | Schema 标注 + Example 正确写法 + Gotchas 解释原因 |
| 4 | 业务规则显式写出 | 枚举等级、过滤条件、术语映射——模型猜不到的都要写 |
| 5 | 表格优于散文 | Schema、枚举值、材料清单等信息用表格呈现 |
| 6 | Join 路径要示范 | description 标注 join key，Example 提供完整 join SQL |
| 7 | description 要精准 | 正面路由覆盖关键词，负面路由防止误用 |
| 8 | 测试驱动迭代 | 每次答错就加一条 Skill 提示，准确率逐步提升 |

### 快速模板

```
my_agent/
├── agent.yaml                        # Agent 配置
├── system_prompt.md                  # 工作流 + 全局约束（不超过 50 行）
└── skills/
    ├── enterprise_basic/SKILL.md     # 每张表一个 Skill
    ├── enterprise_contact/SKILL.md
    ├── enterprise_financing/SKILL.md
    ├── enterprise_product/SKILL.md
    ├── industry/SKILL.md
    ├── industry_enterprise/SKILL.md
    └── users/SKILL.md                # 负面路由示例
```

### 写 Skill 的 5 个检查项

写完 SKILL.md 后，用这 5 个问题自查：

- [ ] **类型陷阱标了吗？** — TEXT 存数字的列，Schema + Example + Gotchas 三处都标注了？
- [ ] **枚举值列全了吗？** — 所有固定取值的列都在 Common values 中列出？有隐式高低的标了顺序？
- [ ] **Join 路径清楚吗？** — description 中标注了 join key？Example 中有完整的 join SQL？
- [ ] **description 够精准吗？** — 正面路由覆盖了用户的不同说法？容易混淆的表加了负面路由？
- [ ] **Example 够有价值吗？** — 每个示例至少展示一个"坑"的正确处理？不是简单的 `SELECT * LIMIT 10`？

---

> 好的数据库 Agent 不是 Prompt 写得多，而是 Skill 写得准。把类型陷阱、业务规则、Join 路径写清楚，让 LLM 在正确的知识框架下写 SQL——这才是数据库 Agent 工程的核心。
