# 数据库场景下如何编写 Skill

> Agent 答错不是因为模型不会写 SQL，而是不了解你的数据库。Skill 就是把你的领域知识传递给模型的方式。本文通过一个企业数据库，教你一步步写出让 Agent 答对的 SKILL.md。

## 目录

- [我们要解决什么问题](#我们要解决什么问题)
- [第一步：审计你的数据库](#第一步审计你的数据库)
- [第二步：处理类型陷阱](#第二步处理类型陷阱)
- [第三步：写出业务规则](#第三步写出业务规则)
- [第四步：引导跨表查询](#第四步引导跨表查询)
- [第五步：写好 description](#第五步写好-description)
- [第六步：测试与迭代](#第六步测试与迭代)
- [完整示例](#完整示例)
- [自查清单](#自查清单)

---

## 我们要解决什么问题

以一个企业数据库为例，7 张表、50 家企业：

| 表名 | 说明 | 关联 |
|------|------|------|
| `enterprise_basic` | 企业基本信息（注册、行业、专精特新等，37 列） | 主表 |
| `enterprise_contact` | 联系人（法人、总经理） | `credit_code` → 主表 |
| `enterprise_financing` | 融资与上市（贷款、估值、上市状态） | `credit_code` → 主表 |
| `enterprise_product` | 产品与知识产权 | `credit_code` → 主表 |
| `industry` | 行业链节点（树结构） | 被映射表引用 |
| `industry_enterprise` | 企业 ↔ 行业链映射 | 连接 industry 和主表 |
| `users` | 平台用户账号 | **独立表，与企业无关** |

没有 Skill 的 Agent 会犯这些错：

- 问"注册资本最高的企业"→ 按字母序排序，"8000" 排在 "50000" 前面（因为 `register_capital` 是 TEXT）
- 问"专精特新小巨人企业"→ 写出 `WHERE zhuanjingtexin_level = '小巨人'`，查不到任何结果
- 问"AI 上游有哪些企业"→ 不知道要三表 join，也不知道 `chain_position='up'` 只在 depth=1 节点上
- 问"平台有多少用户"→ 去查 `enterprise_basic` 而不是 `users`

**这些错误不是模型的问题，是知识缺失的问题。** 下面一步步教你写 Skill 来解决。

---

## 第一步：审计你的数据库

编写 Skill 之前，逐表回答以下问题：

| 问题 | 目的 |
|------|------|
| 这张表存的是什么？一行代表什么？ | 让模型理解业务含义 |
| 哪些列的存储类型和业务含义不匹配？ | 发现类型陷阱（TEXT 存数字） |
| 哪些列只有几个固定取值？ | 列出枚举值，减少猜测 |
| 哪些字段是预计算的？ | 防止模型重复计算 |
| 表之间怎么 join？ | 标注主键和外键 |
| 用户最常问什么？正确的 SQL 怎么写？ | 准备示例查询 |

**每回答一个问题，就往 SKILL.md 里写一条。**

以 `enterprise_basic` 为例：
- 一行 = 一家企业，37 列涵盖注册信息、行业分类、专精特新等级
- `register_capital` 是 TEXT 存数字 → 需要 CAST 提示
- `enterprise_scale` 只有 4 个值（微型/小型/中型/大型）→ 列出枚举
- `zhuanjingtexin_level` 有 3 个等级 + NULL → 列出并标注高低顺序
- 通过 `credit_code` 与其他 enterprise_* 表 join

---

## 第二步：处理类型陷阱

`register_capital`（注册资本）是 TEXT 类型。直接 `ORDER BY register_capital DESC`，"8000" 排在 "50000" 前面——字母序 `"8" > "5"`。

**Skill 中需要在三个地方同时提示**，形成"三点联动"：

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

只写一处，模型可能忽略；三处同时提示，遗漏概率大幅降低。

同理，`enterprise_product.daily_capacity` 也是 TEXT 存数字，需要同样处理。

---

## 第三步：写出业务规则

类型陷阱看 Schema 就能发现，但**业务规则只有了解业务的人才知道**。这是 Skill 最有价值的部分。

**枚举等级**——`zhuanjingtexin_level` 的值有隐含的高低之分：

```
- zhuanjingtexin_level hierarchy:
  专精特新中小企业 < 专精特新潜在"小巨人"企业 < 专精特新"小巨人"企业
  NULL = 无专精特新认定
  "小巨人企业": WHERE zhuanjingtexin_level = '专精特新"小巨人"企业'
```

不写这条，Agent 不知道"小巨人"对应的精确值——它可能写出 `WHERE zhuanjingtexin_level = '小巨人'`，查不到任何结果。

**状态枚举**——`listing_status` 有 4 个值，不同问法对应不同过滤：

```
- listing_status values: 未上市, 新三板, 已上市, 拟上市
  "已上市的企业" = WHERE listing_status = '已上市'
  "有上市计划的" = WHERE listing_status IN ('拟上市', '已上市')
```

**树结构**——`industry` 表不是扁平表，不写清楚层级关系，模型不知道怎么查"AI 上游企业"：

```
- depth=0: chain root, depth=1: 上游/中游/下游, depth=2: leaf nodes
- chain_position ('up'/'mid'/'down') ONLY on depth=1 nodes
- "AI 上游企业" = join industry (chain_position='up') → industry_enterprise → enterprise_basic
```

**容易混淆的表**——`users` 是平台账号，不是企业：

```
- "用户"在本数据库中通常指企业（enterprise_basic），不是平台用户（users）
- 只有明确问"平台管理员"、"登录账号"时才查 users 表
```

---

## 第四步：引导跨表查询

用户问"专精特新小巨人企业中有哪些已上市？"需要 join 两张表。模型需要知道三件事：**用什么 key join**、**join 哪张表**、**完整的 SQL 长什么样**。

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

**在 Example queries 中提供完整 join SQL**：

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

## 第五步：写好 description

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
| `"企业基本信息"` | 太笼统 | `"Use when user asks about registration, location, scale, industry, 专精特新 status"` |
| `"融资表"` | 纯标签 | `"Use when user asks about bank loans, equity, valuation, listing status"` |
| 把 Schema 塞进 description | 浪费 token | description 只放路由提示，Schema 放正文 |

---

## 第六步：测试与迭代

用边界问题验证 Skill 的效果：

- "注册资本最高的企业" → 是否正确 CAST？
- "专精特新小巨人企业有哪些" → 枚举值是否精确匹配？
- "已上市的小巨人企业" → 跨表 join 是否正确？
- "AI 产业链上游有哪些企业" → 三表 join 路径对吗？
- "平台有多少管理员" → 是否走了 users 而不是 enterprise_basic？

**每次 Agent 答错，分析根因并更新 Skill**：

| Agent 的错误 | Skill 如何修改 |
|-------------|---------------|
| 没有读取该 Skill | description 中加入用户使用的关键词 |
| 类型处理错误 | Schema + Gotchas + Example 三处同时加提示 |
| 枚举值写错 | Common values 中加入精确值 |
| Join 写错 | Schema 标注 FK，Example 加 join SQL |
| 误用了错误的表 | description 加强负面路由 |

**Skill 是活文档——每修复一个错误就加一条提示，准确率逐步提升。**

---

## 完整示例

`enterprise_basic` 的 SKILL.md——注意每个章节如何对应前面的步骤：

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
| `register_district` | TEXT | 注册地所在区 (e.g. `海淀区`, `黄浦区`) |
| `register_capital` | TEXT | 注册资本（万元）— **TEXT not numeric**, use `CAST(register_capital AS REAL)` |
| `enterprise_scale` | TEXT | One of `微型`, `小型`, `中型`, `大型` |
| `enterprise_type` | TEXT | One of `民营`, `国有`, `合资`, `外资` |
| `industry_level1` | TEXT | 行业一级分类 (e.g. `制造业`, `金融业`) |
| `zhuanjingtexin_level` | TEXT | 专精特新等级 — see Common values |

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
````

`users` 表——负面路由的示例：

```markdown
---
name: users
description: >-
  Use this skill ONLY when the user explicitly asks about platform users —
  login accounts, SSO ids, roles. This table is unrelated to the enterprise
  tables. Most questions about "用户" actually mean enterprises, not platform users.
---

# users — 平台用户账号

System users of the data platform itself — not enterprises.

## When to use

- "How many platform admins are there?"
- "List all users with the admin role"

**Do NOT use** when the user asks about enterprises, customers, or contacts.
```

---

## 自查清单

写完 SKILL.md 后，逐项检查：

- [ ] **类型陷阱** — TEXT 存数字的列，Schema + Example + Gotchas 三处都标了？
- [ ] **枚举值** — 固定取值的列都列了？有隐式高低的标了顺序？
- [ ] **Join 路径** — description 标了 join key？Example 有完整 join SQL？
- [ ] **description** — 正面路由覆盖了用户的不同说法？容易混淆的表加了负面路由？
- [ ] **Example queries** — 每个示例至少展示一个"坑"的正确处理？

---

> Skill 写得准，Agent 才答得对。把类型陷阱、业务规则、Join 路径写清楚，让模型在正确的知识框架下写 SQL——这就是数据库 Skill 工程的全部。
