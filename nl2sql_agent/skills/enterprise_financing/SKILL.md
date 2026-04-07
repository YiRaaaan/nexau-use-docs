---
name: enterprise_financing
description: Use this skill when the user asks about an enterprise's financing — bank loans, equity rounds, valuation, listing status, planned listing location, or future financing demand. Join with enterprise_basic via credit_code.
---

# enterprise_financing — 企业融资与上市

One row per enterprise summarizing bank-loan history, recent equity financing, valuation, and listing status / progress. Join to `enterprise_basic` via `credit_code`.

## When to use

- "Has enterprise X applied for a bank loan?"
- "What is the most recent valuation of …"
- "List all 已上市 companies on 北交所"
- "Which companies plan to raise more than 10000万 in the next 12 months?"
- "What's the average credit satisfaction rate for 制造业?"

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Internal id |
| `credit_code` | TEXT | Join key |
| `applied_bank_loan` | INTEGER | 是否申请过银行贷款 (0/1) |
| `credit_satisfaction_rate` | REAL | 信贷满足率 (0.0 – 1.0) |
| `loan_purpose` | TEXT | 贷款用途, one of `流动资金`, `设备采购`, `研发投入`, `扩大产能` |
| `next_financing_plan` | TEXT | 下一轮融资计划, one of `暂无`, `12个月内`, `24个月内` |
| `next_financing_demand` | REAL | 下一轮融资需求金额 (万元) |
| `next_financing_method` | TEXT | 融资方式, one of `股权融资`, `债权融资`, `可转债` |
| `recent_equity_financing` | REAL | 最近一轮股权融资金额 (万元) |
| `recent_valuation` | REAL | 最近估值 (万元) |
| `listing_status` | TEXT | One of `未上市`, `新三板`, `已上市`, `拟上市` |
| `stock_code` | TEXT | 股票代码 (empty for unlisted) |
| `listing_progress` | TEXT | 上市进度, one of `无`, `辅导期`, `申报中` |
| `planned_listing_location` | TEXT | 拟上市地点, one of `无`, `上交所`, `深交所`, `北交所`, `港交所` |
| `overseas_listing` | TEXT | `是` / `否` |
| `created_at`, `updated_at` | TEXT | Timestamps |

## Example queries

**Companies with the highest recent valuation:**

```sql
SELECT b.enterprise_name, f.recent_valuation, f.listing_status
FROM enterprise_financing f
JOIN enterprise_basic b ON b.credit_code = f.credit_code
ORDER BY f.recent_valuation DESC
LIMIT 10;
```

**Average financing demand by industry:**

```sql
SELECT b.industry_level1, AVG(f.next_financing_demand) AS avg_demand
FROM enterprise_financing f
JOIN enterprise_basic b ON b.credit_code = f.credit_code
WHERE f.next_financing_plan != '暂无'
GROUP BY b.industry_level1
ORDER BY avg_demand DESC;
```

**Listed companies grouped by exchange:**

```sql
SELECT planned_listing_location, COUNT(*) AS n
FROM enterprise_financing
WHERE listing_status = '已上市'
GROUP BY planned_listing_location;
```
