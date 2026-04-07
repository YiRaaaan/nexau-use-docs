---
name: enterprise_product
description: enterprise_product 是企业主营产品明细表,以 (credit_code, product_index) 为业务键存储每家企业的主要产品信息,包括产品名称、年度产品收入、日产能与产能单位,以及该产品对应的最多三条核心知识产权(专利/商标/著作权)名称。通过 credit_code 与 enterprise_basic 多对一关联。可用于产品收入排名、产能规模分析、知识产权 - 产品挂钩分析等。
---

# enterprise_product

enterprise_product 是企业主营产品明细表,以 (credit_code, product_index) 为业务键存储每家企业的主要产品信息,包括产品名称、年度产品收入、日产能与产能单位,以及该产品对应的最多三条核心知识产权(专利/商标/著作权)名称。通过 credit_code 与 enterprise_basic 多对一关联。可用于产品收入排名、产能规模分析、知识产权 - 产品挂钩分析等。

## 数据表

本技能覆盖以下数据表:

- `enterprise_product`

## 使用场景

- 产品收入排行:按 product_revenue 排序找出高收入产品
- 产能规模统计:按 daily_capacity + capacity_unit 聚合行业产能,需注意单位归一化
- 知识产权-产品关联:通过 ip_name_1/2/3 找出哪些产品有专利支撑,定位创新驱动型产品
- 企业产品多样化分析:GROUP BY credit_code 统计每家企业的产品数量
- 主营产品命名规律分析:对 product_name 做文本分析定位行业关键词

## 空列说明

以下列在当前 mock 数据中没有示例值,使用时需注意:

- `data_source`

## 表详细说明

### enterprise_product

**用途**: enterprise_product 是企业主营产品明细表,以 (credit_code, product_index) 为业务键存储每家企业的主要产品信息,包括产品名称、年度产品收入、日产能与产能单位,以及该产品对应的最多三条核心知识产权(专利/商标/著作权)名称。通过 credit_code 与 enterprise_basic 多对一关联。可用于产品收入排名、产能规模分析、知识产权 - 产品挂钩分析等。

**特点**:
- 本表存储来自数据源的原始数据,包含完整的字段信息
- 支持数据查询、分析和统计需求
- 包含创建与更新时间戳,便于数据追踪

**典型查询**:
- 产品收入排行:按 product_revenue 排序找出高收入产品
- 产能规模统计:按 daily_capacity + capacity_unit 聚合行业产能,需注意单位归一化
- 知识产权-产品关联:通过 ip_name_1/2/3 找出哪些产品有专利支撑,定位创新驱动型产品

## 表结构 DDL

### enterprise_product

```sql
CREATE TABLE enterprise_product (
    id int, -- 自增主键 | examples: [200, 485, 515]
    credit_code text, -- 统一社会信用代码,关联 enterprise_basic | examples: [MOCKCREDIT0000000022, MOCKCREDIT0000000002, MOCKCREDIT0000000015]
    product_index int, -- 产品序号(企业内自增),与 credit_code 组成业务键 | examples: [1, 2, 3]
    product_name text, -- 产品名称 | examples: [垃圾渗滤液处理工艺装备, 弹簧圈栓塞系统, Polaris c1000全自动生化分析]
    product_revenue float, -- 产品年度收入(单位:万元) | examples: [6317.38, 12584.37, 42731.60]
    daily_capacity text, -- 日产能数量(字符串以兼容自由格式) | examples: [4110, 210, 123]
    capacity_unit text, -- 产能计量单位(件/日、吨/日、台/日、套/日 等) | examples: [吨/日, 立方米, 高、中、低]
    ip_name_1 text, -- 关联知识产权 1 的名称(专利/商标/著作权) | examples: [可变光圈驱动马达、摄像装置及电子设备, 打印机和打印介质感测方法, 基于EtherCAT的多设备固件程序并行下载方法及系统]
    ip_name_2 text, -- 关联知识产权 2 的名称 | examples: [一种箱型截面梁自动化柔性切割系统及其切割方法, 一种直直变换器的控制方法, ZL 2016 2 0452812.4]
    ip_name_3 text, -- 关联知识产权 3 的名称 | examples: [一种自修复的固态储氢材料及其制备方法, 一种用3D摄像或照相来监测结晶器内液面波动的方法, 预测锂离子电池循环寿命的方法]
    data_source text, -- 数据来源标识
    created_at text, -- 记录创建时间 | examples: [2025-12-30 16:29:52.783501, 2025-12-30 14:55:52.960307, 2025-12-30 14:56:07.399185]
    updated_at text -- 记录最后更新时间 | examples: [2025-12-30 16:29:52.783501, 2025-12-30 14:55:52.960307, 2025-12-30 14:56:07.399185]
)
```
