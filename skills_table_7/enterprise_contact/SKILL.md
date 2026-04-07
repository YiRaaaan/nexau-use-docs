---
name: enterprise_contact
description: enterprise_contact 是企业联系人信息表,记录每家企业的法人代表、企业高管(总经理)、日常对接联系人三组人员的姓名、职务、座机、手机,以及企业传真、邮箱、控股股东、实际控制人及其国籍。该表通过 credit_code 与 enterprise_basic 一对一关联,用于触达企业、识别控制关系、合规审查等场景。注意:本表含 PII,生产环境查询需脱敏。
---

# enterprise_contact

enterprise_contact 是企业联系人信息表,记录每家企业的法人代表、企业高管(总经理)、日常对接联系人三组人员的姓名、职务、座机、手机,以及企业传真、邮箱、控股股东、实际控制人及其国籍。该表通过 credit_code 与 enterprise_basic 一对一关联,用于触达企业、识别控制关系、合规审查等场景。注意:本表含 PII,生产环境查询需脱敏。

## 数据表

本技能覆盖以下数据表:

- `enterprise_contact`

## 使用场景

- 企业触达:按 credit_code 查询企业法人/总经理/对接人的电话、邮箱以发起业务沟通
- 控制关系识别:通过 controlling_shareholder、actual_controller、actual_controller_nationality 分析企业实控人结构与外资背景
- 高管画像:统计法人代表与高管的职务分布
- 数据完整度审计:检查关键联系字段的填充率,定位需补全的企业
- 合规筛查:筛选 actual_controller_nationality 非中国大陆的企业以满足外资监管要求

## 空列说明

以下列在当前 mock 数据中没有示例值,使用时需注意:

- `data_source`

## 表详细说明

### enterprise_contact

**用途**: enterprise_contact 是企业联系人信息表,记录每家企业的法人代表、企业高管(总经理)、日常对接联系人三组人员的姓名、职务、座机、手机,以及企业传真、邮箱、控股股东、实际控制人及其国籍。该表通过 credit_code 与 enterprise_basic 一对一关联,用于触达企业、识别控制关系、合规审查等场景。注意:本表含 PII,生产环境查询需脱敏。

**特点**:
- 本表存储来自数据源的原始数据,包含完整的字段信息
- 支持数据查询、分析和统计需求
- 包含创建与更新时间戳,便于数据追踪

**典型查询**:
- 企业触达:按 credit_code 查询企业法人/总经理/对接人的电话、邮箱以发起业务沟通
- 控制关系识别:通过 controlling_shareholder、actual_controller、actual_controller_nationality 分析企业实控人结构与外资背景
- 高管画像:统计法人代表与高管的职务分布

## 表结构 DDL

### enterprise_contact

```sql
CREATE TABLE enterprise_contact (
    id int, -- 自增主键 | examples: [45222, 45247, 45261]
    credit_code text, -- 统一社会信用代码,关联 enterprise_basic.credit_code | examples: [MOCKCREDIT0000000010, MOCKCREDIT0000000035, MOCKCREDIT0000000049]
    legal_person_name text, -- 法定代表人姓名(PII) | examples: [REDACTED_1, REDACTED_2, REDACTED_3]
    legal_person_position text, -- 法定代表人职务 | examples: [基金申报主管, 法务总监, 政府事务部总监兼董事长助理]
    legal_person_phone text, -- 法定代表人座机(PII) | examples: [13800000001, 13800000002, 13800000003]
    legal_person_mobile text, -- 法定代表人手机号(PII) | examples: [13800000001, 13800000002, 13800000003]
    manager_name text, -- 企业总经理姓名(PII) | examples: [REDACTED_4, REDACTED_5, REDACTED_6]
    manager_position text, -- 企业总经理职务 | examples: [副总, 人事总监, coo]
    manager_phone text, -- 总经理座机(PII) | examples: [13800000004, 13800000005, 13800000006]
    manager_mobile text, -- 总经理手机号(PII) | examples: [13800000004, 13800000005, 13800000006]
    contact_name text, -- 日常对接联系人姓名(PII) | examples: [REDACTED_1, REDACTED_2, REDACTED_3]
    contact_position text, -- 联系人职务 | examples: [政府事务部主任, 法务总监, 财务经理]
    contact_phone text, -- 联系人座机(PII) | examples: [13800000038, 13800000039, 13800000040]
    contact_mobile text, -- 联系人手机号(PII) | examples: [13800000038, 13800000039, 13800000040]
    fax text, -- 企业传真号码 | examples: [13800000001, 13800000002, 13800000003]
    email text, -- 企业对外联络邮箱(PII) | examples: [user1@example.com, user2@example.com, user3@example.com]
    controlling_shareholder text, -- 控股股东名称 | examples: [REDACTED_38, REDACTED_39, REDACTED_40]
    actual_controller text, -- 实际控制人姓名/名称 | examples: [REDACTED_38, REDACTED_39, REDACTED_40]
    actual_controller_nationality text, -- 实际控制人国籍 | examples: [/, 中华人民共和国, 中国]
    data_source text, -- 数据来源标识
    created_at text, -- 记录创建时间 | examples: [2026-01-14 14:37:22.881765, 2026-01-14 15:09:01.346613, 2026-01-14 15:52:03.620715]
    updated_at text -- 记录最后更新时间 | examples: [2026-01-14 15:54:15.060883, 2026-01-14 15:34:38.634288, 2026-01-14 15:19:55.242603]
)
```
