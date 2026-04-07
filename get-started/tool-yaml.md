# Writing the SQL tools

This is **Step 1** of building the NL2SQL agent. We're going to give the model three tools it can call against the SQLite database:

| Tool | What it does | When the model uses it |
|---|---|---|
| `list_tables` | Lists every table with row counts | First call when exploring an unfamiliar DB |
| `describe_table` | Returns column schema + 3 sample rows | Before writing a SELECT against a table |
| `sql_query` | Executes a read-only SELECT | The actual workhorse |

By the end of this page you'll have a `tools/` folder with three `*.tool.yaml` files and a `bindings.py` that implements all three. They're a runnable unit on their own — you can import them and call them from Python without building the rest of the agent.

## How a NexAU tool is split in two

NexAU tools always have two parts:

- A **`*.tool.yaml`** file holds the *schema* — what the model sees: name, description, parameter types. Edit this when you want to change how the model thinks about the tool.
- A **Python callable** (a plain function) holds the *implementation* — what actually runs when the tool is called. Edit this when the behavior changes.

The two are glued together by the `binding:` field in `agent.yaml`:

```yaml
tools:
  - name: sql_query
    yaml_path: ./tools/sql_query.tool.yaml
    binding: nl2sql_agent.bindings:sql_query
```

Same `module.path:callable` syntax as setuptools entry points. NexAU imports the module and grabs the attribute when the agent loads.

> **Why split them?** Because the YAML is *prompt engineering* — every word in `description` is read by the model and influences when it picks the tool. The Python is *code*. They evolve at different rates, get reviewed by different people, and you want to edit one without touching the other.

## bindings.py — write the implementations first

Start with the easy half: pure Python with no NexAU dependency. Create `nl2sql_agent/bindings.py`:

```python
"""Python tool bindings for the NL2SQL agent.

All tools operate read-only on a SQLite database. The DB path is taken from
the environment variable NL2SQL_DB_PATH (default: mock.sqlite in CWD).
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH_ENV = "NL2SQL_DB_PATH"
DEFAULT_DB_PATH = "mock.sqlite"

# Only SELECT / WITH ... SELECT are allowed. Block any DDL/DML.
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|"
    r"detach|pragma|vacuum|reindex|grant|revoke)\b",
    re.IGNORECASE,
)
_ALLOWED_PREFIX = re.compile(r"^\s*(with|select)\b", re.IGNORECASE)

MAX_ROWS_DEFAULT = 100
MAX_ROWS_HARD = 1000


def _connect() -> sqlite3.Connection:
    p = Path(os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH)).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"SQLite DB not found at {p}")
    # uri=True + mode=ro enforces read-only at the SQLite layer
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
```

That's the shared setup. Now the three tool functions, one at a time.

### `list_tables`

```python
def list_tables() -> dict[str, Any]:
    """List all user tables in the database with row counts."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
        tables = []
        for r in rows:
            name = r["name"]
            count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            tables.append({"name": name, "row_count": count})
    return {"tables": tables}
```

Takes no arguments. Returns a dict with a `tables` array.

### `describe_table`

```python
def describe_table(table_name: str) -> dict[str, Any]:
    """Return the column schema and a few sample rows for a table."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise ValueError(f"Invalid table name: {table_name!r}")

    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        if not exists:
            raise ValueError(f"Table not found: {table_name}")

        cols = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        columns = [
            {
                "name": c["name"], "type": c["type"],
                "notnull": bool(c["notnull"]), "pk": bool(c["pk"]),
            }
            for c in cols
        ]
        sample = [
            dict(r)
            for r in conn.execute(f'SELECT * FROM "{table_name}" LIMIT 3').fetchall()
        ]
        row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

    return {
        "table": table_name,
        "row_count": row_count,
        "columns": columns,
        "sample_rows": sample,
    }
```

Notice the **regex check on `table_name`**. We're interpolating it into a SQL string (you can't bind table names as parameters in SQLite), so we whitelist identifier-shaped values to avoid injection. This is a recurring pattern in tool code: validate at the boundary, then trust internally.

### `sql_query` — the workhorse

```python
def sql_query(query: str, max_rows: int | None = None) -> dict[str, Any]:
    """Execute a read-only SELECT and return rows."""
    if not _ALLOWED_PREFIX.match(query):
        raise ValueError("Only SELECT or WITH ... SELECT queries are allowed.")
    if _FORBIDDEN.search(query):
        raise ValueError("Query contains forbidden keywords.")

    limit = min(max_rows or MAX_ROWS_DEFAULT, MAX_ROWS_HARD)

    with _connect() as conn:
        cursor = conn.execute(query)
        col_names = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(limit + 1)
        truncated = len(rows) > limit
        rows = rows[:limit]

    return {
        "columns": col_names,
        "row_count": len(rows),
        "truncated": truncated,
        "rows": [dict(r) for r in rows],
    }
```

Three layers of safety:

1. **Whitelist prefix.** Only queries starting with `SELECT` or `WITH` get past the gate.
2. **Blacklist keywords.** Reject anything containing `INSERT`, `UPDATE`, `DELETE`, `DROP`, etc. — belt and braces.
3. **Read-only at the SQLite layer.** `_connect()` opens the file with `mode=ro`, so even if a query somehow got through, SQLite would refuse it.

The `truncated` flag tells the model when there were more rows than it asked for, so it can decide whether to refine.

You can test these functions standalone right now, with no NexAU involved:

```bash
python -c "
import os; os.environ['NL2SQL_DB_PATH'] = 'mock.sqlite'
from nl2sql_agent.bindings import list_tables, sql_query
print(list_tables())
print(sql_query('SELECT enterprise_name, register_district FROM enterprise_basic LIMIT 3'))
"
```

This is one of NexAU's nice properties: bindings are plain Python, so unit-testing your tools is just `pytest`.

## tools/list_tables.tool.yaml — write the schema

Now the model-facing half. Create `nl2sql_agent/tools/list_tables.tool.yaml`:

```yaml
type: tool
name: list_tables
description: >-
  List every user table in the connected SQLite database along with its row
  count. Use this as the first step when you need to understand which tables
  are available, or when you want to confirm a table exists before querying
  it. Returns a JSON object with a 'tables' array; each entry has 'name' and
  'row_count'.
input_schema:
  type: object
  properties: {}
  additionalProperties: false
  $schema: http://json-schema.org/draft-07/schema#
```

A few things to call out:

- **`type: tool`** distinguishes a tool YAML from an agent YAML. Required.
- **`name`** is what the model uses to invoke the tool. Match the Python function name to keep your sanity, but they don't strictly have to match — NexAU passes `name` to the model and uses `binding` for execution.
- **`description`** is the prompt the model reads when deciding whether to call this tool. Write it like documentation, not like a code comment. Note how it tells the model *when* to use the tool, not just what it does.
- **`input_schema`** is standard JSON Schema (draft-07). For a no-arg tool you still write an empty `properties: {}` with `additionalProperties: false` to forbid the model from inventing parameters.

## tools/describe_table.tool.yaml

```yaml
type: tool
name: describe_table
description: >-
  Inspect a single table: returns its column schema (name, type, nullability,
  primary key flag), the total row count, and up to 3 sample rows. Use this
  whenever you need to confirm column names, data types, or look at example
  values before writing a SELECT. Prefer this over `sql_query` for schema
  exploration — it is cheaper and safer.
input_schema:
  type: object
  properties:
    table_name:
      type: string
      description: >-
        The exact table name as returned by `list_tables`. Must match
        `[A-Za-z_][A-Za-z0-9_]*`.
  required: [table_name]
  additionalProperties: false
  $schema: http://json-schema.org/draft-07/schema#
```

The description does two things you should always do:

1. Tells the model **when to prefer this tool over a more general one** ("Prefer this over `sql_query` for schema exploration"). The model will follow that hint.
2. Documents the constraint we enforce in code (`[A-Za-z_][A-Za-z0-9_]*`) so the model isn't surprised when validation fails.

## tools/sql_query.tool.yaml

This is the most important schema in the agent. The wording here directly affects how good your NL2SQL ends up.

```yaml
type: tool
name: sql_query
description: >-
  Execute a read-only SQL query against the connected SQLite database and
  return the result rows. Only `SELECT` and `WITH ... SELECT` statements are
  permitted; any DDL/DML keyword (INSERT, UPDATE, DELETE, DROP, ALTER, etc.)
  will be rejected.

  The result includes the column names, the rows (as a list of objects), the
  number of rows returned, and a `truncated` flag indicating whether more
  rows existed than were returned.

  ## When to use

  - Use this only after you've identified the right table(s) via
    `list_tables` and confirmed the columns via `describe_table` or the
    relevant table SKILL.
  - Prefer narrow `SELECT col1, col2 ...` queries over `SELECT *` to keep
    results compact.
  - Always include a `LIMIT` (e.g. `LIMIT 50`) when scanning data — even
    though the tool caps results at `max_rows`, an explicit `LIMIT` is
    cheaper for the database.
  - Use joins on `credit_code` to combine `enterprise_*` tables.

  ## Example

  ```sql
  SELECT enterprise_name, register_capital, register_district
  FROM enterprise_basic
  WHERE enterprise_scale = '小型'
  ORDER BY register_capital DESC
  LIMIT 10;
  ```
input_schema:
  type: object
  properties:
    query:
      type: string
      description: The SQL query to execute. Must start with SELECT or WITH. SQLite dialect.
    max_rows:
      type: integer
      description: >-
        Optional. Maximum number of rows to return (default 100, hard cap
        1000). Set lower if you only need a preview.
  required: [query]
  additionalProperties: false
  $schema: http://json-schema.org/draft-07/schema#
```

What earns this tool description its length:

- A **"When to use"** section that builds the workflow into the tool itself: list → describe → query. The model will follow this even without you saying so in the system prompt.
- An **inline example query** that shows the exact dialect (SQLite), the joining convention (`credit_code`), and the LIMIT habit. Examples in tool descriptions are unreasonably effective.
- An explicit note about the `LIMIT` habit, with the *reason* ("cheaper for the database") so the model can generalize.

You'll write a system prompt later, but as a rule of thumb: **say tool-specific guidance in the tool description, and agent-wide guidance in the system prompt.** This keeps each piece of advice next to the thing it's about.

## What's wired up so far

```
nl2sql_agent/
├── bindings.py
└── tools/
    ├── list_tables.tool.yaml
    ├── describe_table.tool.yaml
    └── sql_query.tool.yaml
```

The tools are complete and testable. They don't know about LLMs, NexAU, or each other — they're just three Python functions and three YAML schemas.

The model still doesn't know what `enterprise_basic.register_capital` *means*, though. That's the job of Skills, which we'll write next.

→ [Writing the table Skills](./skills.md)
