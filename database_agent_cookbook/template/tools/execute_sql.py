"""通用 SQL 执行工具 —— 适用于任意 SQLite 数据库。

数据库路径通过环境变量 DB_PATH 指定。
三层安全：关键字白名单 + 注释剥离 + mode=ro 只读连接。
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

DB_PATH_ENV = "DB_PATH"

MAX_ROWS = 10
MAX_OUTPUT_LENGTH = 50000
DEFAULT_TIMEOUT = 30

_DANGEROUS_KEYWORDS = (
    "DROP", "TRUNCATE", "DELETE", "ALTER", "CREATE",
    "INSERT", "UPDATE", "REPLACE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM", "REINDEX", "GRANT", "REVOKE",
)


def _db_path() -> Path:
    raw = os.environ.get(DB_PATH_ENV, "")
    if not raw:
        raise EnvironmentError(
            f"Environment variable {DB_PATH_ENV} is not set. "
            f"Set it to the path of your SQLite database file."
        )
    p = Path(raw).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"SQLite DB not found at {p}.")
    return p


def _connect() -> sqlite3.Connection:
    uri = f"file:{_db_path()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _strip_sql_comments(sql: str) -> str:
    """剥除 -- 和 /* */ 注释，防止注入绕过。"""
    no_line = re.sub(r"--[^\n]*", "", sql)
    no_block = re.sub(r"/\*.*?\*/", "", no_line, flags=re.DOTALL)
    return no_block


def execute_sql(
    sql: str,
    timeout: int | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """执行一个 SELECT，返回结构化结果。"""
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

    sql_cleaned_upper = _strip_sql_comments(sql).strip().upper()
    for keyword in _DANGEROUS_KEYWORDS:
        if re.match(rf"^{keyword}(?:\s|$)", sql_cleaned_upper):
            return {
                "status": "error",
                "error": f"Only SELECT queries are allowed. Found: {keyword}",
                "sql": sql,
                "duration_ms": int((time.time() - start_time) * 1000),
            }

    if not re.match(r"^(SELECT|WITH)\b", sql_cleaned_upper):
        return {
            "status": "error",
            "error": "Only SELECT or WITH ... SELECT queries are allowed.",
            "sql": sql,
            "duration_ms": int((time.time() - start_time) * 1000),
        }

    connection = None
    try:
        connection = _connect()

        deadline = time.time() + timeout

        def _interrupt_if_expired() -> int:
            return 1 if time.time() > deadline else 0

        connection.set_progress_handler(_interrupt_if_expired, 1000)

        cursor = connection.execute(sql)
        col_names = [d[0] for d in cursor.description] if cursor.description else []

        # Use fetchmany instead of fetchall to avoid loading entire
        # result sets into memory on large tables without LIMIT.
        batch = cursor.fetchmany(max_rows + 1)
        truncated = len(batch) > max_rows
        rows_to_return = batch[:max_rows]
        total_rows = max_rows + 1 if truncated else len(batch)

        duration_ms = int((time.time() - start_time) * 1000)

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

        warnings: list[str] = []
        if total_rows == 0:
            warnings.append(
                "The SQL query returned an empty result. Please review:\n"
                "1. Table name: is the FROM clause correct?\n"
                "2. Column names: do they exist in the target table?\n"
                "3. WHERE conditions: are filters too restrictive?\n"
                "4. Data availability: are the queried columns populated?"
            )
        if truncated:
            warnings.append(
                f"Showing {max_rows} rows (more available). "
                "Consider adding more specific WHERE clauses or LIMIT."
            )

        result: dict[str, Any] = {
            "status": "success",

            "sql": sql,
            "columns": col_names,
            "data": data,
            "row_count": len(data),
            "total_rows": total_rows,
            "truncated": truncated,
            "duration_ms": duration_ms,
        }

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
                    "Consider limiting columns or adding WHERE clauses."
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

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error("SQL execution error: %s", str(e))
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "sql": sql,
            "duration_ms": duration_ms,
        }

    finally:
        if connection is not None:
            connection.close()
