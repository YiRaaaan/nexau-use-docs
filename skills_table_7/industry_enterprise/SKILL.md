---
name: industry_enterprise
description: industry_enterprise 是企业与产业链节点的关联表,记录每家企业被打上了哪些产业链节点标签。以 (industry_id, credit_code) 为复合主键,industry_path 缓存了节点的路径(JSON 数组,包含从根到当前节点的全部 ID),便于直接做产业链层级筛选,无需递归回溯 industry 表。该表是企业-产业链双向检索的核心。
---

# industry_enterprise

industry_enterprise 是企业与产业链节点的关联表,记录每家企业被打上了哪些产业链节点标签。以 (industry_id, credit_code) 为复合主键,industry_path 缓存了节点的路径(JSON 数组,包含从根到当前节点的全部 ID),便于直接做产业链层级筛选,无需递归回溯 industry 表。该表是企业-产业链双向检索的核心。

## 数据表

本技能覆盖以下数据表:

- `industry_enterprise`

## 使用场景

- 按产业链节点查企业:WHERE industry_id = ? 返回某节点上的所有企业
- 按企业查产业链节点:WHERE credit_code = ? 返回该企业被打上的所有标签
- 按产业链祖先节点过滤:利用 industry_path 包含某祖先 ID,聚合该子树下所有企业
- 产业链热度统计:GROUP BY industry_id 计算每个节点的企业数量
- 构造企业-产业的双向 index,用于推荐与匹配

## 表详细说明

### industry_enterprise

**用途**: industry_enterprise 是企业与产业链节点的关联表,记录每家企业被打上了哪些产业链节点标签。以 (industry_id, credit_code) 为复合主键,industry_path 缓存了节点的路径(JSON 数组,包含从根到当前节点的全部 ID),便于直接做产业链层级筛选,无需递归回溯 industry 表。该表是企业-产业链双向检索的核心。

**特点**:
- 本表存储来自数据源的原始数据,包含完整的字段信息
- 支持数据查询、分析和统计需求
- 包含创建与更新时间戳,便于数据追踪

**典型查询**:
- 按产业链节点查企业:WHERE industry_id = ? 返回某节点上的所有企业
- 按企业查产业链节点:WHERE credit_code = ? 返回该企业被打上的所有标签
- 按产业链祖先节点过滤:利用 industry_path 包含某祖先 ID,聚合该子树下所有企业

## 表结构 DDL

### industry_enterprise

```sql
CREATE TABLE industry_enterprise (
    industry_id int, -- 产业链节点 ID,关联 industry.id | examples: [3749, 3750, 3751]
    credit_code text, -- 统一社会信用代码,关联 enterprise_basic.credit_code | examples: [MOCKCREDIT0000000034, MOCKCREDIT0000000023, MOCKCREDIT0000000029]
    created_at text, -- 关联记录创建时间 | examples: [2025-12-26 00:05:28.616484+08:00, 2025-12-26 00:05:14.658525+08:00, 2025-12-26 00:05:04.570944+08:00]
    chain_id int, -- 所属产业链 ID(冗余自 industry.chain_id 便于过滤) | examples: [45, 46, 47]
    industry_path text -- 节点路径(JSON 数组,包含从根到该节点的 ID 序列),用于按祖先快速过滤 | examples: [[4602, 4603, 4604], [4660, 4661, 4664], [4499, 4500, 4501]]
)
```
