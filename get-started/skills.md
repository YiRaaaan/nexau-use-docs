# Writing the table Skills

This is **Step 2**. We've given the agent three tools that can talk to the database, but the model still doesn't know what any of the tables *mean*. `enterprise_basic.register_capital` could be in 元 or 万元 — it doesn't know. `industry_level1` could be a free-text string or a controlled enum — it doesn't know. `users` looks like it might be related to `enterprise_contact` — but it isn't.

Without that knowledge, the agent will guess. We're going to give it the knowledge in a structured, reusable form: **NexAU Skills**.

## What a Skill is

A Skill is a folder containing a `SKILL.md` file (and optional resources). NexAU loads each skill folder you list under `skills:` in `agent.yaml` and prepends its content to the model's context at startup. The format is **Claude-Skill-compatible**, so any skill written for Claude works in NexAU unchanged.

For an NL2SQL agent, the natural unit is **one skill per database table**. This is the design from the [database SKILL design doc](../260407 数据库 SKILL 整理.pdf): each table gets a markdown file describing what it's for, when to use it, what every column means, common values to expect, example queries, and gotchas.

The agent we're building has 7 tables, so we'll write 7 skills:

```
nl2sql_agent/skills/
├── enterprise_basic/SKILL.md
├── enterprise_contact/SKILL.md
├── enterprise_financing/SKILL.md
├── enterprise_product/SKILL.md
├── industry/SKILL.md
├── industry_enterprise/SKILL.md
└── users/SKILL.md
```

## Anatomy of a SKILL.md

Every `SKILL.md` starts with YAML frontmatter and is followed by markdown:

```markdown
---
name: enterprise_basic
description: Use this skill whenever the user asks about an enterprise's identity, registration, location, scale, industry classification, or "专精特新" status. This is the primary table — almost every query about a company starts here. Join other enterprise_* tables to it via credit_code.
---

# enterprise_basic — 企业基本信息

(... markdown body ...)
```

Two fields in the frontmatter, both important:

| Field | Purpose |
|---|---|
| `name` | Stable identifier for the skill. Conventionally matches the folder name. |
| `description` | The **routing prompt** — a one-paragraph summary of when this skill is relevant. The model reads all descriptions and uses them to decide which tables to look at for a given question. **Write this carefully.** |

The `description` is the most important sentence in the file. It is what tells the model "use this skill when…", and a good one is the difference between an agent that picks the right table on the first try and one that thrashes.

## A real example: `enterprise_basic`

Here's the full skill for our central table. We'll dissect each section after.

```markdown
---
name: enterprise_basic
description: Use this skill whenever the user asks about an enterprise's identity, registration, location, scale, industry classification, or "专精特新" status. This is the primary table — almost every query about a company starts here. Join other enterprise_* tables to it via credit_code.
---

# enterprise_basic — 企业基本信息

The central registry of enterprises in the North Nova database. One row per
enterprise, keyed by `credit_code` (统一社会信用代码). Almost every business
question that names a company will join through this table.

## When to use

- "Where is company X registered?" / "What district?"
- "How many small enterprises are there in 海淀区?"
- "List all 专精特新小巨人 enterprises in the manufacturing industry."
- "What is the registered capital of …"

For contact information go to `enterprise_contact`, for financing/listing
go to `enterprise_financing`, for products and IP go to `enterprise_product`,
and for the canonical industry-chain mapping use `industry_enterprise` +
`industry`.

## Schema

| Column | Type | Description |
|---|---|---|
| `credit_code` | TEXT | **Join key.** 统一社会信用代码 — unique enterprise id shared across all `enterprise_*` tables. |
| `enterprise_name` | TEXT | 企业名称 (sanitized in mock as `测试企业_N`) |
| `register_district` | TEXT | 注册地所在区 (e.g. `海淀区`, `黄浦区`, `南山区`) |
| `register_capital` | TEXT | 注册资本 (in 万元 — note this column is TEXT, cast with `CAST(register_capital AS REAL)` for numeric comparisons) |
| `enterprise_scale` | TEXT | One of `微型`, `小型`, `中型`, `大型` |
| `enterprise_type` | TEXT | One of `民营`, `国有`, `合资`, `外资` |
| `industry_level1` – `industry_level4` | TEXT | 行业分类四级编码 (e.g. `制造业` / `专用设备制造业` / ...) |
| `zhuanjingtexin_level` | TEXT | One of `专精特新中小企业`, `专精特新潜在"小巨人"企业`, `专精特新"小巨人"企业`, or NULL |
| ... | ... | ... |

## Common values to know

- `enterprise_scale`: `微型`, `小型`, `中型`, `大型`
- `enterprise_type`: `民营`, `国有`, `合资`, `外资`
- `industry_level1` examples: `制造业`, `信息传输、软件和信息技术服务业`, ...

## Example queries

**Top 10 small enterprises by registered capital in 海淀区:**

\```sql
SELECT enterprise_name,
       CAST(register_capital AS REAL) AS capital_wan,
       enterprise_scale
FROM enterprise_basic
WHERE register_district = '海淀区'
  AND enterprise_scale = '小型'
ORDER BY capital_wan DESC
LIMIT 10;
\```

**Count of 专精特新 enterprises by level:**

\```sql
SELECT zhuanjingtexin_level, COUNT(*) AS n
FROM enterprise_basic
WHERE zhuanjingtexin_level IS NOT NULL
GROUP BY zhuanjingtexin_level
ORDER BY n DESC;
\```

## Gotchas

- `register_capital` is **TEXT**, not numeric — cast it with `CAST(register_capital AS REAL)` whenever you compare or sort numerically.
- `enterprise_name` is sanitized — every value looks like `测试企业_N`. If the user asks about a real company by name, explain that this is mock data.
```

The full file lives at [`nl2sql_agent/skills/enterprise_basic/SKILL.md`](../nl2sql_agent/skills/enterprise_basic/SKILL.md).

## Anatomy: what each section is for

A good table SKILL has six sections in this order. They map to the six things a model needs to know to write a correct query.

### 1. One-paragraph overview

What this table is and what it's keyed by. Two or three sentences max. The model uses this to confirm it picked the right table after the description routed it here.

### 2. **When to use**

A list of natural-language question patterns that should trigger this skill, plus pointers to **other** skills for adjacent concerns. The pointers matter as much as the inclusions — they prevent the model from doing everything in one table when it should be joining.

```markdown
For contact information go to `enterprise_contact`, for financing/listing
go to `enterprise_financing`, ...
```

This is how skills become a graph rather than a list.

### 3. **Schema**

A table with `column | type | description`. Don't just paste DDL — write the description in business language. Note units (`in 万元`), encoding tricks (`stored as TEXT`), and the join keys (`**Join key.**`).

This is the densest part of the skill and the one that prevents the model from inventing columns.

### 4. **Common values to know**

For columns with a small set of valid values, list them. For example:

```markdown
- `enterprise_scale`: `微型`, `小型`, `中型`, `大型`
- `zhuanjingtexin_level`: `专精特新中小企业` < `专精特新潜在"小巨人"企业` < `专精特新"小巨人"企业`
```

This is the difference between the model writing `WHERE enterprise_scale = 'small'` (broken) and `WHERE enterprise_scale = '小型'` (correct). It also lets you encode ordering when relevant.

### 5. **Example queries**

Two or three SQL examples that show:

- The dialect (SQLite syntax)
- Common WHERE patterns for this table
- How to join to other tables
- Aggregations / grouping you'd typically want

The model will pattern-match on these. They're worth their weight in tokens.

### 6. **Gotchas**

Anything weird about the table that will bite the model:

- "`register_capital` is TEXT, cast with `CAST(... AS REAL)`"
- "`industry_level1` has noisy values like `26 化学原料和化学制品制造业` — use `LIKE`"
- "An enterprise may have 0 rows here — use `LEFT JOIN` if you need every enterprise"

These usually surface during testing — when the model writes a wrong query, look at *why* it was wrong, and add that as a gotcha to the relevant skill. The skill is self-improving.

## A second example: when *not* to use

Some tables look related but aren't. The `users` table in our database is the platform login table, not enterprise contacts — confusing them is the most natural mistake an agent will make. So that skill leads with a "do NOT use" hint:

```markdown
---
name: users
description: Use this skill ONLY when the user explicitly asks about platform users — login accounts, SSO ids, roles. This table is unrelated to the enterprise tables and should not be joined to them. Most NL2SQL questions about "用户" actually mean enterprises, not platform users — confirm with the user if ambiguous.
---

# users — 平台用户账号

System users of the data platform itself — not enterprises. Use this only
when the user asks about login accounts, SSO, or platform roles. If the user
says "用户" without context, they almost always mean enterprises
(`enterprise_basic`); ask before assuming.

**Do NOT use this skill** when the user asks about enterprises, customers,
contacts, or any business-domain "user" — those live in `enterprise_basic`
and `enterprise_contact`.
```

Negative routing — telling the model when *not* to pick something — is just as important as positive routing. A skill is allowed (and encouraged) to push the model away from itself.

## Wiring skills into the agent

Once your skills are written, you reference them by folder path in `agent.yaml`:

```yaml
skills:
  - ./skills/enterprise_basic
  - ./skills/enterprise_contact
  - ./skills/enterprise_financing
  - ./skills/enterprise_product
  - ./skills/industry
  - ./skills/industry_enterprise
  - ./skills/users
```

Paths are relative to the YAML file. NexAU walks each folder, reads `SKILL.md`, parses the frontmatter, and injects the body into the agent's context at startup.

## Tips for writing good table skills

- **One skill per table.** Don't merge related tables into one skill — the model needs to be able to "decide" which one applies, and merging hides that decision.
- **Lead with the description.** If you only have time to write one good sentence, make it the frontmatter description.
- **Use real example values.** `WHERE enterprise_scale = '小型'` teaches the model the encoding far better than "the scale column has Chinese values."
- **Document storage quirks.** TEXT-stored numbers, JSON-in-TEXT columns, sanitized fields, soft-deleted rows. The model can't see these; you have to tell it.
- **Update skills when you fix bugs.** Each time you correct a wrong query the agent generated, add the lesson to the relevant skill's "Gotchas" section. Skills are the agent's long-term memory.
- **Generate, don't hand-write, for big schemas.** For 70+ tables, write a one-time script that samples each table and asks an LLM to draft the skill — the design doc that inspired this layout describes exactly that workflow.

## What's wired up so far

```
nl2sql_agent/
├── bindings.py
├── tools/
│   ├── list_tables.tool.yaml
│   ├── describe_table.tool.yaml
│   └── sql_query.tool.yaml
└── skills/
    ├── enterprise_basic/SKILL.md
    ├── enterprise_contact/SKILL.md
    ├── enterprise_financing/SKILL.md
    ├── enterprise_product/SKILL.md
    ├── industry/SKILL.md
    ├── industry_enterprise/SKILL.md
    └── users/SKILL.md
```

Tools are written. Skills are written. The only thing missing is the file that ties them all together — the agent YAML.

→ [Writing the agent YAML](./agent-yaml.md)
