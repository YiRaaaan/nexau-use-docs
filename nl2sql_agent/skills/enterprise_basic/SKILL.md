---
name: enterprise_basic
description: Use this skill whenever the user asks about an enterprise's identity, registration, location, scale, industry classification, or "专精特新" status. This is the primary table — almost every query about a company starts here. Join other enterprise_* tables to it via credit_code.
---

# enterprise_basic — 企业基本信息

The central registry of enterprises in the North Nova database. One row per enterprise, keyed by `credit_code` (统一社会信用代码). Almost every business question that names a company will join through this table.

## When to use

- "Where is company X registered?" / "What district?"
- "How many small enterprises are there in 海淀区?"
- "List all 专精特新小巨人 enterprises in the manufacturing industry."
- "What is the registered capital of …"
- "Which industry does enterprise X belong to?"

For contact information go to `enterprise_contact`, for financing/listing go to `enterprise_financing`, for products and IP go to `enterprise_product`, and for the canonical industry-chain mapping use `industry_enterprise` + `industry`.

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Internal row id |
| `credit_code` | TEXT | **Join key.** 统一社会信用代码 — the unique enterprise identifier shared across all `enterprise_*` tables. |
| `enterprise_name` | TEXT | 企业名称 (sanitized in mock as `测试企业_N`) |
| `declaration_year` | TEXT | 申报年度, e.g. `2021（新）`, `2024` |
| `data_batch` | TEXT | Internal batch tag (`MOCK_BATCH_xxx` in this mock) |
| `sequence_number` | INTEGER | Per-batch sequence index |
| `register_district` | TEXT | 注册地所在区 (e.g. `海淀区`, `黄浦区`, `南山区`) |
| `jurisdiction_district` | TEXT | 管辖区 (often differs from `register_district`) |
| `street` | TEXT | 街道 |
| `register_address` | TEXT | 注册地址 (full street address) |
| `correspondence_address` | TEXT | 通讯地址 |
| `postal_code` | TEXT | 邮编 |
| `register_date` | TEXT | 注册日期, ISO date string |
| `register_capital` | TEXT | 注册资本 (in 万元 — note this column is TEXT, cast with `CAST(register_capital AS REAL)` for numeric comparisons) |
| `register_capital_currency` | TEXT | Almost always `人民币` |
| `enterprise_scale` | TEXT | One of `微型`, `小型`, `中型`, `大型` |
| `enterprise_type` | TEXT | One of `民营`, `国有`, `合资`, `外资` |
| `foreign_capital_ratio` | REAL | 外资占比 (0.0 – 1.0) |
| `industry_level1` – `industry_level4` | TEXT | 行业分类四级编码 (e.g. `制造业` / `专用设备制造业` / `医疗仪器设备及器械制造` / `医疗诊断、监护及治疗设备制造`). For the chain-graph view of industries use `industry_enterprise`. |
| `main_product_service` | TEXT | 主营产品/服务的简短描述 |
| `main_product_category` | TEXT | 主营产品类别 |
| `market_years` | INTEGER | 上市年限 |
| `enterprise_introduction` | TEXT | 企业简介 (long text) |
| `website` | TEXT | 企业官网 |
| `declaration_type` | TEXT | 申报类型, e.g. `更新`, `新增` |
| `zhuanjingtexin_level` | TEXT | 专精特新等级 — one of `专精特新中小企业`, `专精特新潜在"小巨人"企业`, `专精特新"小巨人"企业`, or NULL |
| `financial_outlier_analysis` | INTEGER | 财务异常分析结果 (in mock: `无异常` / `轻微异常`) |
| `municipal_high_level_enterprise` | INTEGER | 是否市级高水平企业 (0/1) |
| `created_at`, `updated_at` | TEXT | ISO timestamps |
| `unicorn_category`, `unicorn_year` | TEXT / INTEGER | 独角兽分类与入选年度 |
| `legal_entity_data` | TEXT (JSON) | 法人主体数据 — JSON blob with `establish_year`, `employee_count`, `reg_no` |

## Common values to know

- `enterprise_scale`: `微型`, `小型`, `中型`, `大型`
- `enterprise_type`: `民营`, `国有`, `合资`, `外资`
- `zhuanjingtexin_level`: `专精特新中小企业` < `专精特新潜在"小巨人"企业` < `专精特新"小巨人"企业`
- `industry_level1` examples: `制造业`, `信息传输、软件和信息技术服务业`, `科学研究和技术服务业`, `金融业`

## Example queries

**Top 10 small enterprises by registered capital in 海淀区:**

```sql
SELECT enterprise_name,
       CAST(register_capital AS REAL) AS capital_wan,
       enterprise_scale
FROM enterprise_basic
WHERE register_district = '海淀区'
  AND enterprise_scale = '小型'
ORDER BY capital_wan DESC
LIMIT 10;
```

**Count of 专精特新 enterprises by level:**

```sql
SELECT zhuanjingtexin_level, COUNT(*) AS n
FROM enterprise_basic
WHERE zhuanjingtexin_level IS NOT NULL
GROUP BY zhuanjingtexin_level
ORDER BY n DESC;
```

**Join with financing to find listed manufacturing companies:**

```sql
SELECT b.enterprise_name, b.industry_level2, f.listing_status, f.stock_code
FROM enterprise_basic b
JOIN enterprise_financing f ON b.credit_code = f.credit_code
WHERE b.industry_level1 = '制造业'
  AND f.listing_status = '已上市';
```

## Gotchas

- `register_capital` is **TEXT**, not numeric — cast it with `CAST(register_capital AS REAL)` whenever you compare or sort numerically.
- `industry_level1` in this mock is somewhat noisy (some rows have a numeric prefix like `26 化学原料和化学制品制造业`). Use `LIKE '%制造%'` for fuzzy matching.
- `enterprise_name` is sanitized — every value looks like `测试企业_N`. If the user asks about a real company by name, explain that this is mock data.
