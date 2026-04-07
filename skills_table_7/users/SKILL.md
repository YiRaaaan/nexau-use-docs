---
name: users
description: users 是系统用户表,存储平台账号信息,支持本地账号与单点登录(SSO)双模式。包含 sso_user_id(SSO 唯一标识)、display_name(展示名)、email、role(角色)、username/password_hash(本地登录凭证)以及 sso_raw_data(SSO 原始 JSON 资料快照)。用于鉴权、审计、按角色过滤功能权限等场景。注意:本表含 PII 与凭证,严格按需脱敏访问。
---

# users

users 是系统用户表,存储平台账号信息,支持本地账号与单点登录(SSO)双模式。包含 sso_user_id(SSO 唯一标识)、display_name(展示名)、email、role(角色)、username/password_hash(本地登录凭证)以及 sso_raw_data(SSO 原始 JSON 资料快照)。用于鉴权、审计、按角色过滤功能权限等场景。注意:本表含 PII 与凭证,严格按需脱敏访问。

## 数据表

本技能覆盖以下数据表:

- `users`

## 使用场景

- 登录鉴权:按 username + password_hash 或 sso_user_id 校验用户身份
- 角色过滤:按 role 字段判定用户的功能权限范围
- 用户审计:按 created_at、updated_at 跟踪账号生命周期
- SSO 数据回查:从 sso_raw_data JSON 字段中提取额外的 SSO 属性
- 用户列表展示:按 display_name、email 检索与展示

## 表详细说明

### users

**用途**: users 是系统用户表,存储平台账号信息,支持本地账号与单点登录(SSO)双模式。包含 sso_user_id(SSO 唯一标识)、display_name(展示名)、email、role(角色)、username/password_hash(本地登录凭证)以及 sso_raw_data(SSO 原始 JSON 资料快照)。用于鉴权、审计、按角色过滤功能权限等场景。注意:本表含 PII 与凭证,严格按需脱敏访问。

**特点**:
- 本表存储来自数据源的原始数据,包含完整的字段信息
- 支持数据查询、分析和统计需求
- 包含创建与更新时间戳,便于数据追踪

**典型查询**:
- 登录鉴权:按 username + password_hash 或 sso_user_id 校验用户身份
- 角色过滤:按 role 字段判定用户的功能权限范围
- 用户审计:按 created_at、updated_at 跟踪账号生命周期

## 表结构 DDL

### users

```sql
CREATE TABLE users (
    id int, -- 自增主键 | examples: [1, 2, 3]
    sso_user_id text, -- 单点登录系统中的用户唯一 ID | examples: [REDACTED]
    display_name text, -- 用户展示名(PII) | examples: [REDACTED_1, REDACTED_2, REDACTED_3]
    email text, -- 用户邮箱(PII) | examples: [user1@example.com, user2@example.com, user3@example.com]
    role text, -- 用户角色(user / admin / 等),用于权限控制 | examples: [admin, user]
    created_at text, -- 账号创建时间 | examples: [2025-12-23 14:52:07.082594, 2026-02-04 11:34:29.608171, 2025-12-30 21:18:23.738812]
    updated_at text, -- 账号最后更新时间 | examples: [2026-01-29 08:46:29.994000, 2026-01-29 06:26:44.890000, 2025-12-23 14:52:07.082594]
    sso_raw_data text, -- SSO 返回的用户原始资料(JSON 字符串) | examples: [REDACTED]
    password_hash text, -- 本地登录密码的哈希值(凭证,严禁明文返回) | examples: [REDACTED]
    username text -- 本地登录用户名 | examples: [REDACTED_1, REDACTED_8, REDACTED_15]
)
```
