---
name: industry
description: industry 是产业链节点维表,以树形结构存储某条产业链上的所有节点(上游/中游/下游与各级细分),通过 (chain_id, parent_id, depth, sort_order, path) 表达层级和顺序,name 为节点名称,description 为该节点的业务定义。chain_position 标识节点在链条中的位置(up/middle/down),icon 提供前端图标名。该表是产业链可视化与企业-产业链映射(industry_enterprise)的基础。
---

# industry

industry 是产业链节点维表,以树形结构存储某条产业链上的所有节点(上游/中游/下游与各级细分),通过 (chain_id, parent_id, depth, sort_order, path) 表达层级和顺序,name 为节点名称,description 为该节点的业务定义。chain_position 标识节点在链条中的位置(up/middle/down),icon 提供前端图标名。该表是产业链可视化与企业-产业链映射(industry_enterprise)的基础。

## 数据表

本技能覆盖以下数据表:

- `industry`

## 使用场景

- 产业链可视化:递归遍历 parent_id 渲染树状或链状产业图谱
- 节点检索:按 name、description 关键词搜索定位特定产业环节
- 上下游分析:按 chain_position 区分上游基础设施 / 中游制造 / 下游应用
- 层级统计:按 depth 统计每层节点数量,衡量产业链复杂度
- 为企业打标:通过 path 与 industry_enterprise 关联,实现企业到产业链节点的快速归类

## 表详细说明

### industry

**用途**: industry 是产业链节点维表,以树形结构存储某条产业链上的所有节点(上游/中游/下游与各级细分),通过 (chain_id, parent_id, depth, sort_order, path) 表达层级和顺序,name 为节点名称,description 为该节点的业务定义。chain_position 标识节点在链条中的位置(up/middle/down),icon 提供前端图标名。该表是产业链可视化与企业-产业链映射(industry_enterprise)的基础。

**特点**:
- 本表存储来自数据源的原始数据,包含完整的字段信息
- 支持数据查询、分析和统计需求
- 包含创建与更新时间戳,便于数据追踪

**典型查询**:
- 产业链可视化:递归遍历 parent_id 渲染树状或链状产业图谱
- 节点检索:按 name、description 关键词搜索定位特定产业环节
- 上下游分析:按 chain_position 区分上游基础设施 / 中游制造 / 下游应用

## 表结构 DDL

### industry

```sql
CREATE TABLE industry (
    id int, -- 节点主键 | examples: [3747, 3748, 3749]
    chain_id int, -- 所属产业链 ID,标识节点归属哪一条产业链 | examples: [45, 46, 47]
    parent_id int, -- 父节点 ID,根节点为 NULL | examples: [3747, 3748, 3758]
    name text, -- 节点名称(如 上游 / 算力基础设施 / 大模型 / 应用层 等) | examples: [注册申报与合规服务, 自动驾驶测试与认证, 感知组件与智能硬件]
    description text, -- 节点的业务定义与说明,可较长 | examples: [覆盖类风湿、银屑病、炎症性肠病等，治疗以生物制剂与小分子免疫调节为主。关键在于长期疗效与安全性、患者分层与用药管理。, 用于SLAM、手眼协调与质检的高性能摄像头、结构光模组与ToF深度相机。, 面向科研与大规模训练的超算/智算集群，涵盖计算节点、互联网络、并行存储、作业系统与运维体系。其核心是系统集成与调优：通过拓扑设计、通信/IO优化与资源调度...]
    path text, -- 从根到当前节点的路径(JSON 数组形式存储 ID 序列) | examples: [[3821, 3859], [3877, 3878], [4464, 4480]]
    depth int, -- 节点深度(根为 0) | examples: [0, 1, 2]
    sort_order int, -- 同级节点的排序权重 | examples: [8, 9, 7]
    created_at text, -- 创建时间 | examples: [2025-12-26 00:05:28.616484+08:00, 2025-12-26 00:05:14.658525+08:00, 2025-12-26 00:05:04.570944+08:00]
    updated_at text, -- 更新时间 | examples: [2025-12-26 00:05:28.616484+08:00, 2025-12-26 00:05:14.658525+08:00, 2025-12-26 00:05:04.570944+08:00]
    chain_position text, -- 在产业链上的位置标识(up=上游 / middle=中游 / down=下游) | examples: [down, mid, up]
    icon text -- 前端展示用的图标名(如 arrow-up-from-line) | examples: [monitor, plug-zap, warehouse]
)
```
