"""从任意 SQLite 数据库自动生成每张表的 SKILL.md。

用法:
    python generate_skills.py mydb.sqlite                  # 输出到 ./skills/
    python generate_skills.py mydb.sqlite -o ./my_skills   # 指定输出目录
    python generate_skills.py mydb.sqlite --tables users,orders  # 只生成指定表

生成的 SKILL.md 包含：
  - frontmatter（name + description 占位）
  - Schema 表（列名 / 类型 / PK/FK 标注）
  - Common values（每列至多 8 个最常见的值）
  - Example queries（自动生成 2-3 个）
  - Gotchas（自动检测 TEXT 存数字、NULL 比例高等常见坑）

生成后建议人工审阅并补充：
  1. description 中的路由关键词（"何时使用"）
  2. 业务含义说明（列的中文名、枚举值的语义）
  3. 更多示例 SQL
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Any


def _get_tables(conn: sqlite3.Connection) -> list[str]:
    """获取所有用户表（排除 sqlite_ 内部表）。"""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def _get_table_info(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    """获取表结构信息。"""
    rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    cols = []
    for r in rows:
        cols.append({
            "cid": r[0],
            "name": r[1],
            "type": r[2] or "TEXT",
            "notnull": bool(r[3]),
            "default": r[4],
            "pk": bool(r[5]),
        })
    return cols


def _get_foreign_keys(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    """获取外键映射 {local_col: "ref_table.ref_col"}。"""
    rows = conn.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()
    fk_map: dict[str, str] = {}
    for r in rows:
        fk_map[r[3]] = f"{r[2]}.{r[4]}"
    return fk_map


def _get_row_count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]


def _get_common_values(
    conn: sqlite3.Connection, table: str, col: str, limit: int = 8
) -> list[tuple[str, int]]:
    """获取某列最常见的值及出现次数。跳过 NULL。"""
    try:
        rows = conn.execute(
            f"SELECT [{col}], COUNT(*) AS n FROM [{table}] "
            f"WHERE [{col}] IS NOT NULL "
            f"GROUP BY [{col}] ORDER BY n DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(str(r[0]), r[1]) for r in rows]
    except Exception:
        return []


def _get_null_ratio(conn: sqlite3.Connection, table: str, col: str) -> float:
    """某列 NULL 值占比。"""
    try:
        row = conn.execute(
            f"SELECT COUNT(*) FILTER (WHERE [{col}] IS NULL) * 1.0 / COUNT(*) "
            f"FROM [{table}]"
        ).fetchone()
        return row[0] if row and row[0] is not None else 0.0
    except Exception:
        # SQLite < 3.30 不支持 FILTER，用子查询
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
            if total == 0:
                return 0.0
            nulls = conn.execute(
                f"SELECT COUNT(*) FROM [{table}] WHERE [{col}] IS NULL"
            ).fetchone()[0]
            return nulls / total
        except Exception:
            return 0.0


def _is_numeric_in_text(
    conn: sqlite3.Connection, table: str, col: str
) -> bool:
    """检测 TEXT 列是否实际存储数字（常见坑：价格、资本等）。"""
    try:
        sample = conn.execute(
            f"SELECT [{col}] FROM [{table}] WHERE [{col}] IS NOT NULL LIMIT 20"
        ).fetchall()
        if not sample:
            return False
        numeric_count = sum(
            1 for r in sample
            if r[0] is not None and re.match(r"^-?\d+(\.\d+)?$", str(r[0]).strip())
        )
        return numeric_count / len(sample) > 0.8
    except Exception:
        return False


def _get_sample_row(conn: sqlite3.Connection, table: str) -> dict[str, Any] | None:
    """获取一行样本数据。"""
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"SELECT * FROM [{table}] LIMIT 1").fetchone()
        conn.row_factory = None
        if row:
            return dict(row)
    except Exception:
        conn.row_factory = None
    return None


def generate_skill(conn: sqlite3.Connection, table: str) -> str:
    """为一张表生成 SKILL.md 内容。"""
    columns = _get_table_info(conn, table)
    fk_map = _get_foreign_keys(conn, table)
    row_count = _get_row_count(conn, table)

    # ── PK 列 ──
    pk_cols = [c["name"] for c in columns if c["pk"]]
    pk_str = ", ".join(f"`{c}`" for c in pk_cols) if pk_cols else "（无显式 PK）"

    # ── FK 说明 ──
    fk_notes = []
    for local_col, ref in fk_map.items():
        fk_notes.append(f"`{local_col}` → `{ref}`")

    # ── description 占位 ──
    fk_hint = ""
    if fk_map:
        fk_hint = " Join keys: " + ", ".join(fk_notes) + "."

    description = (
        f"Use this skill whenever the user asks about data in the `{table}` "
        f"table.{fk_hint} "
        f"[TODO: Add specific routing keywords — what kinds of questions "
        f"should trigger reading this Skill?]"
    )

    # ── Schema 表 ──
    schema_rows = []
    for col in columns:
        parts = []
        type_str = col["type"]
        if col["pk"]:
            parts.append("PK")
        if col["name"] in fk_map:
            parts.append(f"FK → `{fk_map[col['name']]}`")
        if col["notnull"] and not col["pk"]:
            parts.append("NOT NULL")
        if col["default"] is not None:
            parts.append(f"default: {col['default']}")
        desc = " · ".join(parts) if parts else ""
        schema_rows.append(f"| `{col['name']}` | {type_str} | {desc} |")

    schema_block = "\n".join(schema_rows)

    # ── Common values ──
    common_value_sections = []
    for col in columns:
        if col["type"].upper() in ("INTEGER", "REAL", "NUMERIC", "BLOB"):
            continue
        if col["pk"]:
            continue
        values = _get_common_values(conn, table, col["name"])
        if not values or len(values) > 50:
            continue
        distinct_count = len(values)
        # 只有少量不同值时才列出（枚举型列）
        total_for_col = sum(v[1] for v in values)
        if distinct_count <= 10 and total_for_col > 0:
            val_strs = [f"`{v[0]}`" for v in values]
            common_value_sections.append(
                f"- `{col['name']}`: {', '.join(val_strs)}"
            )

    common_values_block = ""
    if common_value_sections:
        common_values_block = (
            "## Common values\n\n" + "\n".join(common_value_sections)
        )

    # ── Gotchas ──
    gotchas = []
    for col in columns:
        # TEXT 列存数字
        if col["type"].upper() == "TEXT":
            if _is_numeric_in_text(conn, table, col["name"]):
                gotchas.append(
                    f"`{col['name']}` is **TEXT** but stores numeric values — "
                    f"use `CAST({col['name']} AS REAL)` for numeric comparisons "
                    f"and sorting."
                )
        # 高 NULL 比例
        null_ratio = _get_null_ratio(conn, table, col["name"])
        if null_ratio > 0.3 and not col["pk"]:
            pct = int(null_ratio * 100)
            gotchas.append(
                f"`{col['name']}` has ~{pct}% NULL values. "
                f"Filter with `WHERE {col['name']} IS NOT NULL` if aggregating."
            )

    gotchas_block = ""
    if gotchas:
        gotchas_block = "## Gotchas\n\n" + "\n".join(f"- {g}" for g in gotchas)
    else:
        gotchas_block = (
            "## Gotchas\n\n"
            "- [TODO: Add known pitfalls — type mismatches, naming quirks, "
            "semantic traps.]"
        )

    # ── Example queries ──
    examples = []

    # Example 1: 简单 SELECT + LIMIT
    select_cols = [c["name"] for c in columns[:5]]
    col_list = ", ".join(f"[{c}]" for c in select_cols)
    examples.append(
        f"**Browse the table:**\n\n```sql\n"
        f"SELECT {col_list}\nFROM [{table}]\nLIMIT 10;\n```"
    )

    # Example 2: 如果有 TEXT 枚举列，按它 GROUP BY
    for col in columns:
        if col["type"].upper() == "TEXT" and not col["pk"] and col["name"] not in fk_map:
            vals = _get_common_values(conn, table, col["name"], limit=5)
            if 2 <= len(vals) <= 10:
                examples.append(
                    f"**Count by `{col['name']}`:**\n\n```sql\n"
                    f"SELECT [{col['name']}], COUNT(*) AS n\n"
                    f"FROM [{table}]\nGROUP BY [{col['name']}]\n"
                    f"ORDER BY n DESC;\n```"
                )
                break

    # Example 3: 如果有 FK，生成 JOIN 示例
    if fk_map:
        fk_col, ref = next(iter(fk_map.items()))
        ref_table, ref_col = ref.split(".")
        examples.append(
            f"**Join with `{ref_table}`:**\n\n```sql\n"
            f"SELECT t.*, r.*\nFROM [{table}] t\n"
            f"JOIN [{ref_table}] r ON t.[{fk_col}] = r.[{ref_col}]\n"
            f"LIMIT 10;\n```"
        )

    examples_block = "## Example queries\n\n" + "\n\n".join(examples)

    # ── 组装 ──
    sections = [
        f"---\nname: {table}\ndescription: >-\n  {description}\n---\n",
        f"# {table}\n",
        f"Rows: **{row_count}** · PK: {pk_str}",
    ]

    if fk_notes:
        sections.append(
            "Foreign keys: " + ", ".join(fk_notes)
        )

    sections.append(
        "\n## When to use\n\n"
        "- [TODO: Add 3–5 example questions that should trigger this Skill]\n"
    )

    sections.append(
        f"## Schema\n\n"
        f"| Column | Type | Description |\n"
        f"|---|---|---|\n"
        f"{schema_block}\n"
    )

    if common_values_block:
        sections.append(common_values_block + "\n")

    sections.append(examples_block + "\n")
    sections.append(gotchas_block + "\n")

    return "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从 SQLite 数据库自动生成每张表的 SKILL.md"
    )
    parser.add_argument("db", help="SQLite 数据库文件路径")
    parser.add_argument(
        "-o", "--output", default="./skills",
        help="输出目录（默认 ./skills）"
    )
    parser.add_argument(
        "--tables",
        help="只生成指定表（逗号分隔，如 users,orders）"
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        raise SystemExit(1)

    output_dir = Path(args.output)

    conn = sqlite3.connect(str(db_path))

    tables = _get_tables(conn)
    if args.tables:
        selected = {t.strip() for t in args.tables.split(",")}
        tables = [t for t in tables if t in selected]
        missing = selected - set(tables)
        if missing:
            print(f"⚠️  未找到表: {', '.join(missing)}")

    if not tables:
        print("❌ 没有找到任何表")
        conn.close()
        raise SystemExit(1)

    print(f"📊 数据库: {db_path}")
    print(f"📁 输出目录: {output_dir}")
    print(f"📋 表: {', '.join(tables)}\n")

    for table in tables:
        skill_dir = output_dir / table
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        content = generate_skill(conn, table)
        skill_file.write_text(content, encoding="utf-8")
        print(f"  ✅ {skill_file}")

    conn.close()

    print(f"\n🎉 共生成 {len(tables)} 个 SKILL.md")
    print(
        "\n💡 下一步：\n"
        "   1. 编辑每个 SKILL.md 的 description（添加路由关键词）\n"
        "   2. 补充 'When to use' 示例问题\n"
        "   3. 补充业务含义说明和 Gotchas\n"
        "   4. 在 agent.yaml 的 skills: 中注册"
    )


if __name__ == "__main__":
    main()
