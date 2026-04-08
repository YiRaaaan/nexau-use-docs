---
name: users
description: Use this skill ONLY when the user explicitly asks about platform users — login accounts, SSO ids, roles. This table is unrelated to the enterprise tables and should not be joined to them. Most natural-language questions about "用户" actually mean enterprises, not platform users — confirm with the user if ambiguous.
---

# users — 平台用户账号

System users of the data platform itself — not enterprises. Use this only when the user asks about login accounts, SSO, or platform roles. If the user says "用户" without context, they almost always mean enterprises (`enterprise_basic`); ask before assuming.

## When to use

- "How many platform admins are there?"
- "List all users with the admin role"
- "When was user X created?"

**Do NOT use this skill** when the user asks about enterprises, customers, contacts, or any business-domain "user" — those live in `enterprise_basic` and `enterprise_contact`.

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Internal id |
| `sso_user_id` | TEXT | SSO subject id (redacted in mock) |
| `display_name` | TEXT | 显示名 (redacted) |
| `email` | TEXT | 邮箱 (sanitized as `userN@example.com`) |
| `role` | TEXT | One of `user`, `admin` |
| `created_at`, `updated_at` | TEXT | Timestamps |
| `sso_raw_data` | TEXT | Raw SSO claims (redacted to empty) |
| `password_hash` | TEXT | Local password hash (redacted) |
| `username` | TEXT | Local username (redacted) |

## Example queries

**Counts by role:**

```sql
SELECT role, COUNT(*) AS n FROM users GROUP BY role;
```

**Most recently created accounts:**

```sql
SELECT id, role, created_at FROM users ORDER BY created_at DESC LIMIT 10;
```

## Privacy

Every personally identifying field in this table is redacted. Do not pretend the values represent real users.
