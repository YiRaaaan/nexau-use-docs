---
name: enterprise_basic
description: enterprise_basic 是企业基础信息主表,存储申报主体的工商注册要素(信用代码、企业名称、注册地、注册资本、注册日期等)、行业分类(国民经济行业四级)、申报属性(申报年度、申报类型、专精特新等级、独角兽分类)及法人实体快照。该表是企业域所有子表(联系人、融资、产品、产业链)通过 credit_code 进行 JOIN 的核心。可用于企业画像、行业分布统计、申报批次跟踪、专精特新/独角兽筛选与质量审计等场景。
---

# enterprise_basic

enterprise_basic 是企业基础信息主表,存储申报主体的工商注册要素(信用代码、企业名称、注册地、注册资本、注册日期等)、行业分类(国民经济行业四级)、申报属性(申报年度、申报类型、专精特新等级、独角兽分类)及法人实体快照。该表是企业域所有子表(联系人、融资、产品、产业链)通过 credit_code 进行 JOIN 的核心。可用于企业画像、行业分布统计、申报批次跟踪、专精特新/独角兽筛选与质量审计等场景。

## 数据表

本技能覆盖以下数据表:

- `enterprise_basic`

## 使用场景

- 企业画像查询:按 credit_code 或 enterprise_name 定位企业的注册、规模、行业、资本等基本信息
- 行业分布统计:按 industry_level1 ~ industry_level4 进行四级行业聚合统计
- 专精特新筛选:通过 zhuanjingtexin_level、declaration_type、declaration_year 找出特定批次的入选企业
- 独角兽企业分析:用 unicorn_category、unicorn_year 筛选独角兽企业并按行业/年份分组
- 区域招商分析:按 register_district、jurisdiction_district 统计辖区内企业数量与规模分布
- 数据治理:用 data_batch、created_at、updated_at 进行批次比对和数据更新审计

## 空列说明

以下列在当前 mock 数据中没有示例值,使用时需注意:

- `data_source`

## 表详细说明

### enterprise_basic

**用途**: enterprise_basic 是企业基础信息主表,存储申报主体的工商注册要素(信用代码、企业名称、注册地、注册资本、注册日期等)、行业分类(国民经济行业四级)、申报属性(申报年度、申报类型、专精特新等级、独角兽分类)及法人实体快照。该表是企业域所有子表(联系人、融资、产品、产业链)通过 credit_code 进行 JOIN 的核心。可用于企业画像、行业分布统计、申报批次跟踪、专精特新/独角兽筛选与质量审计等场景。

**特点**:
- 本表存储来自数据源的原始数据,包含完整的字段信息
- 支持数据查询、分析和统计需求
- 包含创建与更新时间戳,便于数据追踪

**典型查询**:
- 企业画像查询:按 credit_code 或 enterprise_name 定位企业的注册、规模、行业、资本等基本信息
- 行业分布统计:按 industry_level1 ~ industry_level4 进行四级行业聚合统计
- 专精特新筛选:通过 zhuanjingtexin_level、declaration_type、declaration_year 找出特定批次的入选企业

## 表结构 DDL

### enterprise_basic

```sql
CREATE TABLE enterprise_basic (
    id int, -- 自增主键,内部唯一行 ID | examples: [1, 2, 3]
    credit_code text, -- 统一社会信用代码,企业的法定唯一标识,跨表 JOIN 的主键 | examples: [MOCKCREDIT0000000001, MOCKCREDIT0000000002, MOCKCREDIT0000000003]
    enterprise_name text, -- 企业法定全称 | examples: [测试企业_1, 测试企业_2, 测试企业_3]
    declaration_year text, -- 申报年度,用于按年份维度过滤申报批次 | examples: [2024（新）, 2023（复）, 2024年]
    data_batch text, -- 数据批次号,标识本条记录所属的导入批次 | examples: [1, 第二批, 4]
    sequence_number int, -- 申报序号,批次内的排序编号 | examples: [1, 2, 3]
    register_district text, -- 注册地行政区划(区/县) | examples: [上海, 上海市 市辖区 临港新片区, 上海市 市辖区 嘉定区]
    jurisdiction_district text, -- 管辖地行政区划(区/县),通常与注册地相同 | examples: [临港新片区, 嘉定区, 奉贤区]
    street text, -- 注册街道 | examples: [天平路街道, 奉投集团, 罗泾镇]
    register_address text, -- 注册地详细地址 | examples: [上海市杨浦区国康路98号801室, 上海市金山区亭林镇林盛路193弄100号, 上海市嘉定区墨玉路185号1层J]
    correspondence_address text, -- 通讯/办公地址 | examples: [上海市浦东新区兰花路333号世纪大厦603室, 上海市杨浦区国康路98号801室, 上海市金山区亭林镇林盛路193弄100号]
    postal_code text, -- 邮政编码 | examples: [202162, 518055, 201101.0]
    register_date text, -- 工商注册成立日期 | examples: [2016-09-27, 1995-02-10, 1993-01-12]
    register_capital text, -- 注册资本(单位:万元),按 register_capital_currency 标识币种 | examples: [2529.78（人民币）, 4003.5786, 3322.1467]
    register_capital_currency text, -- 注册资本币种(人民币/美元/港币等) | examples: [人民币, 日元, 欧元]
    enterprise_scale text, -- 企业规模分类(微型/小型/中型/大型) | examples: [大型, 微型, 中型]
    enterprise_type text, -- 企业经济类型(内资/合资/外资/有限责任公司等) | examples: [有限责任公司(外商投资企业与内资合资), 股份有限公司(港澳台投资、未上市), 有限责任公司(港澳台投资、非独资)]
    foreign_capital_ratio float, -- 外资比例(0~1 之间的小数),用于内外资统计 | examples: [0.00, 0.10, 0.20]
    industry_level1 text, -- 国民经济行业分类一级(门类) | examples: [制造业-汽车制造业, 42 废弃资源综合利用业, 信息传输、软件和信息技术服务业-互联网和相关服务]
    industry_level2 text, -- 国民经济行业分类二级(大类) | examples: [电信、广播电视和卫星传输服务, 互联网-互联网服务-网络媒体, 非金属矿物制品业]
    industry_level3 text, -- 国民经济行业分类三级(中类) | examples: [铁路、道路、隧道和桥梁工程建筑, 7499 其他未列明专业技术服务业, 其他未列明金融业]
    industry_level4 text, -- 国民经济行业分类四级(小类) | examples: [太阳能发电工程施工, 环保技术推广服务, 鸡的饲养]
    main_product_service text, -- 主营产品/服务的简短描述 | examples: [有机肥料；微生物肥料；生物炭基肥料；水溶肥料；复合微生物肥料, 智能建筑系统集成服务, VR漫游大师]
    main_product_category text, -- 主营产品大类标签 | examples: [4102040204 磁致伸缩液位计, 研究与试验发展服务-医学研究与试验发展服务-基础医学研究服务-基础医学研究服务-基础医学研究服务, 体育服务-其他体育服务]
    market_years int, -- 进入市场年限(年) | examples: [87, 29, 68]
    enterprise_introduction text, -- 企业自我介绍/简介长文本 | examples: [测试企业 1 是一家专注于智能新能源领域的高新技术企业,主要从事绿色新材料服务的研发与生产,产品广泛应用于多个行业。本介绍为脱敏占位文本,仅供本地开发使用。, 测试企业 2 是一家专注于新能源新能源领域的高新技术企业,主要从事高端半导体平台的研发与生产,产品广泛应用于多个行业。本介绍为脱敏占位文本,仅供本地开发使用。, 测试企业 3 是一家专注于信息工业领域的高新技术企业,主要从事半导体新能源系统的研发与生产,产品广泛应用于多个行业。本介绍为脱敏占位文本,仅供本地开发使用。]
    website text, -- 企业官方网站 URL | examples: [https://example.com/mock/1, https://example.com/mock/2, https://example.com/mock/3]
    declaration_type text, -- 申报类型(新申报/复审/更新/专精特新中小企业/小巨人等) | examples: [申请, 复核, 更新]
    zhuanjingtexin_level text, -- 专精特新等级标签(如 专精特新中小企业 / 小巨人 / 单项冠军) | examples: [专精特新潜在"小巨人"企业, 专精特新"小巨人"企业, 专精特新中小企业]
    financial_outlier_analysis int, -- 财务异常分析结果(0=无异常 / 1=有异常 等编码) | examples: [False, True]
    municipal_high_level_enterprise int, -- 是否市级高新技术企业的二值标识(0/1) | examples: [True]
    data_source text, -- 数据来源标识,记录条目的导入来源
    created_at text, -- 记录创建时间 | examples: [2026-01-14 15:09:03.589722, 2026-01-14 15:01:16.015392, 2026-01-14 14:59:00.079074]
    updated_at text, -- 记录最后更新时间 | examples: [2026-01-14 15:40:46.145689, 2026-01-14 15:50:00.600985, 2026-01-14 15:46:58.115789]
    unicorn_category text, -- 独角兽企业分类(独角兽/潜在独角兽/瞪羚等),非独角兽为空 | examples: [已上市独角兽企业, 独角兽企业, 独角兽潜力企业]
    unicorn_year int, -- 认定为独角兽的年份 | examples: [2024]
    legal_entity_data text -- 法人实体补充数据(JSON 字符串),包含登记号、成立年份、员工数等结构化字段 | examples: [{"mock": true, "row": 1, "reg_no": "MOCKREG4146634219", "establish_year": 200..., {"mock": true, "row": 2, "reg_no": "MOCKREG2668662088", "establish_year": 199..., {"mock": true, "row": 3, "reg_no": "MOCKREG6347278151", "establish_year": 199...]
)
```
