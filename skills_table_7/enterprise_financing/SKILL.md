---
name: enterprise_financing
description: enterprise_financing 是企业融资与资本市场信息表,记录企业的银行授信申请情况、授信满足率、贷款用途、未来融资计划与金额、近期股权融资额与估值、上市状态(未上市/新三板/已上市)、股票代码、计划上市进度与目的地等。通过 credit_code 与 enterprise_basic 一对一关联。可用于资金面分析、上市辅导筛选、估值排行、融资缺口识别等金融场景。
---

# enterprise_financing

enterprise_financing 是企业融资与资本市场信息表,记录企业的银行授信申请情况、授信满足率、贷款用途、未来融资计划与金额、近期股权融资额与估值、上市状态(未上市/新三板/已上市)、股票代码、计划上市进度与目的地等。通过 credit_code 与 enterprise_basic 一对一关联。可用于资金面分析、上市辅导筛选、估值排行、融资缺口识别等金融场景。

## 数据表

本技能覆盖以下数据表:

- `enterprise_financing`

## 使用场景

- 上市企业筛选:按 listing_status 找出已上市/拟上市企业,结合 stock_code 关联行情
- 融资需求分析:按 next_financing_demand、next_financing_method 统计未来融资规模与方式分布
- 估值排行:按 recent_valuation 排序找出高估值企业
- 授信满足度分析:通过 credit_satisfaction_rate 评估银行对中小企业的授信落地情况
- 上市辅导跟踪:按 listing_progress、planned_listing_location 跟踪进入辅导期或申报期的企业
- 海外上市监测:按 overseas_listing 标识筛选拟在境外/已在境外上市的企业

## 空列说明

以下列在当前 mock 数据中没有示例值,使用时需注意:

- `data_source`

## 表详细说明

### enterprise_financing

**用途**: enterprise_financing 是企业融资与资本市场信息表,记录企业的银行授信申请情况、授信满足率、贷款用途、未来融资计划与金额、近期股权融资额与估值、上市状态(未上市/新三板/已上市)、股票代码、计划上市进度与目的地等。通过 credit_code 与 enterprise_basic 一对一关联。可用于资金面分析、上市辅导筛选、估值排行、融资缺口识别等金融场景。

**特点**:
- 本表存储来自数据源的原始数据,包含完整的字段信息
- 支持数据查询、分析和统计需求
- 包含创建与更新时间戳,便于数据追踪

**典型查询**:
- 上市企业筛选:按 listing_status 找出已上市/拟上市企业,结合 stock_code 关联行情
- 融资需求分析:按 next_financing_demand、next_financing_method 统计未来融资规模与方式分布
- 估值排行:按 recent_valuation 排序找出高估值企业

## 表结构 DDL

### enterprise_financing

```sql
CREATE TABLE enterprise_financing (
    id int, -- 自增主键 | examples: [1, 2, 3]
    credit_code text, -- 统一社会信用代码,关联 enterprise_basic | examples: [MOCKCREDIT0000000001, MOCKCREDIT0000000002, MOCKCREDIT0000000003]
    applied_bank_loan int, -- 是否申请过银行贷款的二值标识(0/1) | examples: [False, True]
    credit_satisfaction_rate float, -- 授信满足率(0~1 之间的小数),银行实际授信/申请额度 | examples: [35.00, 79.68, 3.45]
    loan_purpose text, -- 贷款用途(流动资金/设备采购/研发投入/扩大产能等) | examples: [日常生产经营,研发及技术改造,扩大生产, 研发及技术改造,海外分支机构运营及投资并购, 研发及技术改造,扩大生产]
    next_financing_plan text, -- 下一轮融资计划时间窗(暂无/12个月内/24个月内等) | examples: [12个月内, 暂无, 24个月内]
    next_financing_demand float, -- 下一轮融资需求金额(单位:万元) | examples: [2000.00, 3200.00, 30000.00]
    next_financing_method text, -- 下一轮融资方式(股权融资/债权融资/可转债等) | examples: [,股权融资,上市融资, ,银行贷款,其他,股权融资, ,银行贷款,股权融资,债券融资]
    recent_equity_financing float, -- 近期完成的股权融资金额(万元) | examples: [222.56, 14940.00, 666912.00]
    recent_valuation float, -- 近期估值(万元),用于估值排行与变化分析 | examples: [29358.00, 39500.00, 10500.00]
    listing_status text, -- 上市状态(未上市/新三板/已上市/拟上市) | examples: [拟上市, 辅导备案, 新三板上市]
    stock_code text, -- 证券代码,已上市企业才有 | examples: [(09688.HK)(ZLAB.US), /, 0]
    listing_progress text, -- 上市进度(无/辅导期/申报中等) | examples: [中止, 处理中, 已完成上市前股改]
    planned_listing_location text, -- 计划上市地点(上交所/深交所/北交所/港交所等) | examples: [,上交所 主板, ,上交所 主板,上交所 科创板, ,上交所 主板,深交所 主板,深交所 创业板]
    overseas_listing text, -- 是否在境外上市的二值标识(是/否) | examples: [/, H股, NASDAQ：NAMI]
    data_source text, -- 数据来源标识
    created_at text, -- 记录创建时间 | examples: [2026-01-14 15:49:47.395951, 2026-01-14 15:48:04.643732, 2026-01-14 15:47:18.946406]
    updated_at text -- 记录最后更新时间 | examples: [2026-01-14 15:34:11.536932, 2026-01-14 15:47:33.814413, 2026-01-14 15:32:43.077953]
)
```
