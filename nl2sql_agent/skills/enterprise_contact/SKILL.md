---
name: enterprise_contact
description: Use this skill when the user asks about enterprise contact information — legal person, manager, primary contact, phone/email/fax, controlling shareholder, or actual controller. Join with enterprise_basic on credit_code.
---

# enterprise_contact — 企业联系人信息

One row per enterprise containing all contact and ownership-control fields. Joined to `enterprise_basic` via `credit_code`.

> **Sanitization notice.** In this mock all personal-identifier fields are redacted: names appear as `REDACTED_N`, phones as `138NNNNNNNN`, emails as `userN@example.com`, and shareholder fields are NULL. Treat absence of data as a sanitization artifact, not as a real-world signal.

## When to use

- "Who is the legal person of company X?"
- "Show me the contact phone for enterprise X"
- "Which enterprises share the same actual controller?"
- "Find all enterprises whose legal person is also the manager"

## Schema

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Internal id |
| `credit_code` | TEXT | Join key to `enterprise_basic` |
| `legal_person_name` | TEXT | 法人姓名 (redacted) |
| `legal_person_position` | TEXT | 法人职务, e.g. `董事长兼首席执行官` |
| `legal_person_phone` | TEXT | 法人座机 (redacted) |
| `legal_person_mobile` | TEXT | 法人手机 (redacted) |
| `manager_name` | TEXT | 总经理姓名 (redacted) |
| `manager_position` | TEXT | 总经理职务 |
| `manager_phone` | TEXT | 总经理座机 |
| `manager_mobile` | TEXT | 总经理手机 |
| `contact_name` | TEXT | 主要联系人姓名 (redacted) |
| `contact_position` | TEXT | 联系人职务 |
| `contact_phone` | TEXT | 联系人座机 |
| `contact_mobile` | TEXT | 联系人手机 |
| `fax` | TEXT | 传真 |
| `email` | TEXT | 联系邮箱 |
| `controlling_shareholder` | TEXT | 控股股东 (redacted) |
| `actual_controller` | TEXT | 实际控制人 (redacted) |
| `actual_controller_nationality` | TEXT | 实控人国籍 |
| `created_at`, `updated_at` | TEXT | Timestamps |

## Example queries

**List the legal-person position for the first 10 enterprises:**

```sql
SELECT b.enterprise_name, c.legal_person_position
FROM enterprise_contact c
JOIN enterprise_basic b ON b.credit_code = c.credit_code
LIMIT 10;
```

**Enterprises whose legal person also serves as manager:**

```sql
SELECT b.enterprise_name
FROM enterprise_contact c
JOIN enterprise_basic b ON b.credit_code = c.credit_code
WHERE c.legal_person_name = c.manager_name
  AND c.legal_person_name IS NOT NULL;
```
