import json
import os
from pathlib import Path

# 配置文件路径
table_schema_file = "./table_descriptions.json"
skill_files_dir = "./skills_table_70"

# 创建输出目录
Path(skill_files_dir).mkdir(parents=True, exist_ok=True)

# 读取表描述数据
with open(table_schema_file, "r", encoding="utf-8") as f:
    tables = json.load(f)

print(f"开始转换 {len(tables)} 个表...")

for table in tables:
    table_name = table["table_name"]
    overview = table["overview"]
    usage_scenarios = table.get("usage_scenarios", [])
    empty_columns = table.get("empty_columns", [])
    columns = table.get("columns", [])

    # 创建表对应的目录
    table_dir = Path(skill_files_dir) / table_name
    table_dir.mkdir(parents=True, exist_ok=True)

    # 生成 SKILL.md 内容
    print(f"正在生成 {table_name} 的 SKILL.md 文件")
    skill_content = f"""---
name: {table_name}
description: {overview}
---

# {table_name}

{overview}

## 数据表

本技能覆盖以下数据表：

- `{table_name}`

## 使用场景

"""
    # 添加使用场景
    if usage_scenarios:
        for scenario in usage_scenarios:
            skill_content += f"- {scenario}\n"
    else:
        skill_content += "- 暂无使用场景信息\n"

    # 添加空列信息
    if empty_columns:
        skill_content += f"""
## 空列说明

以下列目前为空，使用时需注意：

"""
        for col in empty_columns:
            skill_content += f"- `{col}`\n"

    # 添加表详细说明
    skill_content += f"""
## 表详细说明

### {table_name}

**用途**: {overview}

**特点**:
- 本表存储来自数据源的原始数据，包含完整的字段信息
- 支持数据查询、分析和统计需求
- 包含创建与更新时间戳，便于数据追踪

**典型查询**:
- 查询表中的所有字段信息
- 根据业务需求进行数据筛选和统计
- 关联其他表进行综合分析

"""
    # 添加表结构 DDL
    skill_content += f"""
## 表结构 DDL

### {table_name}

```sql
CREATE TABLE {table_name} (
"""
    # 生成 DDL 字段
    for i, col in enumerate(columns):
        col_name = col.get("name", "")
        col_type = col.get("data_type", "text")

        # 转换数据类型为 SQL 格式
        if col_type == "text":
            sql_type = "text"
        elif col_type == "int" or col_type == "integer":
            sql_type = "int"
        elif col_type == "bigint":
            sql_type = "bigint"
        elif col_type == "float" or col_type == "double":
            sql_type = "float"
        elif col_type == "date":
            sql_type = "date"
        elif col_type == "timestamp" or col_type == "datetime":
            sql_type = "timestamp without time zone"
        elif col_type == "boolean" or col_type == "bool":
            sql_type = "boolean"
        else:
            sql_type = "text"

        # 添加注释
        col_meaning = col.get("meaning", "")
        col_examples = col.get("examples", [])
        is_empty = col.get("is_empty", False)
        
        # 构建注释内容
        comment_parts = []
        if col_meaning:
            comment_parts.append(col_meaning)
        # 只有当列不为空且有示例值时，才添加examples
        if not is_empty and col_examples:
            # 将示例值转换为字符串
            examples_str = ", ".join(str(example) for example in col_examples)
            comment_parts.append(f"examples: [{examples_str}]")
        
        comment = f" -- {' | '.join(comment_parts)}" if comment_parts else ""

        # 判断是否是最后一个字段
        if i == len(columns) - 1:
            skill_content += f"    {col_name} {sql_type}{comment}\n"
        else:
            skill_content += f"    {col_name} {sql_type},{comment}\n"

    skill_content += """)\n```\n"""

    # 写入文件
    skill_file = table_dir / "SKILL.md"
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(skill_content)

    print(f"已生成: {skill_file}")

print(f"\n完成！共生成 {len(tables)} 个 skill 文件")
print(f"输出目录: {skill_files_dir}")