"""Python tool bindings for the NL2SQL agent.

Exposes a single `execute_sql` tool with the same signature, return shape and
safety pattern as NexEvo's `nl2sql.tools.sql_tool:execute_sql`, so this agent
stays drop-in consistent with the upstream ChatBI tool surface. The backend is
SQLite (read-only) instead of asyncpg/PostgreSQL.

The DB path is taken from the env var ``NL2SQL_DB_PATH`` (default:
``enterprise.sqlite`` in the current working directory).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH_ENV = "NL2SQL_DB_PATH"
DEFAULT_DB_PATH = "enterprise.sqlite"

MAX_ROWS = 10
MAX_OUTPUT_LENGTH = 50000
DEFAULT_TIMEOUT = 30

# Block any DDL/DML keyword. Matches NexEvo's list, plus a few SQLite-specific
# verbs (ATTACH/DETACH/PRAGMA/VACUUM/REINDEX/REPLACE) that can read or mutate
# state in ways a SELECT-only tool should not allow.
_DANGEROUS_KEYWORDS = (
    "DROP",
    "TRUNCATE",
    "DELETE",
    "ALTER",
    "CREATE",
    "INSERT",
    "UPDATE",
    "REPLACE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "GRANT",
    "REVOKE",
)


def _db_path() -> Path:
    p = Path(os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH)).expanduser()
    if not p.exists():
        raise FileNotFoundError(
            f"SQLite DB not found at {p}. Set {DB_PATH_ENV} or run from a "
            f"directory containing {DEFAULT_DB_PATH}."
        )
    return p


def _connect() -> sqlite3.Connection:
    # uri=True + mode=ro enforces read-only at the SQLite layer
    uri = f"file:{_db_path()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _strip_sql_comments(sql: str) -> str:
    """Remove `-- ...` and `/* ... */` comments so they can't bypass the
    leading-keyword check (e.g. ``-- foo\\nUPDATE``)."""
    no_line = re.sub(r"--[^\n]*", "", sql)
    no_block = re.sub(r"/\*.*?\*/", "", no_line, flags=re.DOTALL)
    return no_block


def execute_sql(
    sql: str,
    timeout: int | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Execute a SELECT against the SQLite mock and return rows.

    Args:
        sql: SQL query (SELECT / WITH ... SELECT only).
        timeout: Timeout in seconds (default 30). Enforced via SQLite's
            progress handler.
        max_rows: Max rows to return (default 10).

    Returns a dict with: status, command_status, sql, columns, data,
    row_count, total_rows, truncated, duration_ms, optionally warnings.
    On error: status="error", error, error_type, sql, duration_ms.
    """
    start_time = time.time()

    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    if max_rows is None:
        max_rows = MAX_ROWS

    if not sql or not sql.strip():
        return {
            "status": "error",
            "error": "SQL query cannot be empty",
            "duration_ms": int((time.time() - start_time) * 1000),
        }

    # Strip comments before scanning, so attackers can't hide a write behind
    # `-- ...\nUPDATE ...`.
    sql_cleaned_upper = _strip_sql_comments(sql).strip().upper()
    for keyword in _DANGEROUS_KEYWORDS:
        if re.match(rf"^{keyword}(?:\s|$)", sql_cleaned_upper):
            return {
                "status": "error",
                "error": f"Only SELECT queries are allowed. Found: {keyword}",
                "sql": sql,
                "duration_ms": int((time.time() - start_time) * 1000),
            }
    # Also require a SELECT-shaped statement at the front.
    if not re.match(r"^(SELECT|WITH)\b", sql_cleaned_upper):
        return {
            "status": "error",
            "error": "Only SELECT or WITH ... SELECT queries are allowed.",
            "sql": sql,
            "duration_ms": int((time.time() - start_time) * 1000),
        }

    connection: sqlite3.Connection | None = None
    try:
        connection = _connect()

        # Wall-clock timeout via progress handler.
        deadline = time.time() + timeout

        def _interrupt_if_expired() -> int:
            return 1 if time.time() > deadline else 0

        connection.set_progress_handler(_interrupt_if_expired, 1000)

        cursor = connection.execute(sql)
        col_names = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()

        duration_ms = int((time.time() - start_time) * 1000)

        total_rows = len(rows)
        truncated = total_rows > max_rows
        rows_to_return = rows[:max_rows] if truncated else rows

        # SQLite values are already JSON-friendly (str/int/float/bytes/None).
        data: list[dict[str, Any]] = []
        for row in rows_to_return:
            d = dict(row)
            for key, value in list(d.items()):
                if isinstance(value, (bytes, bytearray)):
                    d[key] = value.hex()
                elif not isinstance(
                    value, (str, int, float, bool, type(None), list, dict)
                ):
                    d[key] = str(value)
            data.append(d)

        # SQLite has no equivalent of PG's command-status string; synthesize
        # one so the return shape matches NexEvo's tool exactly.
        command_status = f"SELECT {total_rows}"

        warnings: list[str] = []
        if total_rows == 0:
            warnings.append(
                "The SQL query returned an empty result. Please review and "
                "confirm the following:\n"
                "1. Table selection: Ensure the FROM clause references the "
                "correct table name\n"
                "2. Column selection: Verify column names exist in the target "
                "table\n"
                "3. WHERE clause conditions: Check if filter conditions are too "
                "restrictive or incorrect\n"
                "4. Data availability: Consider if the columns you're querying "
                "are empty."
            )
        if truncated:
            warnings.append(
                "Query results were truncated due to row limit. Consider "
                "limiting the number of columns or adding more specific WHERE "
                "clauses."
            )

        result: dict[str, Any] = {
            "status": "success",
            "command_status": command_status,
            "sql": sql,
            "columns": col_names,
            "data": data,
            "row_count": len(data),
            "total_rows": total_rows,
            "truncated": truncated,
            "duration_ms": duration_ms,
        }

        # Length-based truncation: shrink rows from the tail until the JSON
        # serialization fits MAX_OUTPUT_LENGTH.
        if len(json.dumps(result, ensure_ascii=False)) > MAX_OUTPUT_LENGTH:
            while (
                len(data) > 1
                and len(json.dumps(result, ensure_ascii=False)) > MAX_OUTPUT_LENGTH
            ):
                data = data[:-1]
                result["data"] = data
                result["row_count"] = len(data)
                result["truncated"] = True
            if not any("row limit" in w for w in warnings):
                warnings.append(
                    "Query results were truncated due to length limit. "
                    "Consider limiting the number of columns or adding more "
                    "specific WHERE clauses."
                )

        if warnings:
            result["warnings"] = warnings

        logger.info(
            "SQL executed successfully: rows=%d, duration=%dms",
            total_rows,
            duration_ms,
        )
        return result

    except sqlite3.OperationalError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        msg = str(e)
        # `interrupted` is what the progress handler raises on deadline.
        if "interrupted" in msg.lower():
            return {
                "status": "timeout",
                "error": f"Query timed out after {timeout} seconds",
                "sql": sql,
                "duration_ms": duration_ms,
            }
        logger.error("SQL execution error: %s", msg)
        return {
            "status": "error",
            "error": msg,
            "error_type": type(e).__name__,
            "sql": sql,
            "duration_ms": duration_ms,
        }

    except Exception as e:  # noqa: BLE001
        duration_ms = int((time.time() - start_time) * 1000)
        msg = str(e)
        logger.error("SQL execution error: %s", msg)
        return {
            "status": "error",
            "error": msg,
            "error_type": type(e).__name__,
            "sql": sql,
            "duration_ms": duration_ms,
        }

    finally:
        if connection is not None:
            connection.close()
