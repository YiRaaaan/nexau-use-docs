# 第 2 章 · 编写自定义 SQL 工具

## 第 1 章的痛点回顾

第 1 章的 Agent 可以运行，但存在四个明显的代价：

- **结果是 stdout 字符串**——LLM 自行数空格、对齐列名，容易出错
- **安全依赖 system prompt**——模型一旦未遵守约束，就可能实际执行 `DELETE`
- **每次调用 fork 一个 sqlite3 进程**——延迟和资源开销更高
- **LLM 不知道列名，每次都要先 `.schema` 探查一次**

第 2 章一次性解决前三项，方式是用一个自定义 Python 工具替换 `run_shell_command`（列名问题留待第 3 章用 Skills 解决）。本章所介绍的不仅是"如何编写一个 SQL 工具"，更是 NexAU 中所有自定义工具都遵循的统一模式——一份 Python 实现加一份 YAML schema，通过 `binding` 在 `agent.yaml` 中绑定。

## 一个 NexAU 工具由两部分组成

NexAU 中每个工具对应两个文件：

| 部分 | 文件 | 受众 |
|---|---|---|
| schema | `tools/<Name>.tool.yaml` | 面向 LLM：名称、描述、参数 |
| 实现 | `tools/<name>.py` 中的一个函数 | 面向机器：实际执行的代码 |

两者通过 `agent.yaml` 中的 `binding:` 字段关联。

之所以拆分为两份，是因为它们的演化速度不同。schema 中的每一个词都会影响"模型何时选择该工具、传入什么参数"，修改 description 属于提示工程，需要反复调优;实现部分是普通 Python，修改它属于编码与测试。将两者置于独立文件中，修改一方时无需触及另一方。

以下按此顺序展开：实现 → schema → 在 `agent.yaml` 中绑定 → 修改系统提示。

## 编写实现 —— `tools/execute_sql.py`

在 `enterprise_data_agent/tools/` 下创建 `execute_sql.py`（schema 和实现放在同一个 `tools/` 目录中）。首先是初始化部分：

```python
"""企业数据分析 Agent 的工具实现:一个安全的只读 execute_sql。"""

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

DB_PATH_ENV = "ENTERPRISE_DB_PATH"
# 相对于本文件解析: tools/execute_sql.py → parent.parent = agent 根目录。
# Cloud 上 enterprise.sqlite 位于 agent 根目录; 本地 start.py 通过
# ENTERPRISE_DB_PATH 环境变量覆盖。
DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent / "enterprise.sqlite")

MAX_ROWS = 10
MAX_OUTPUT_LENGTH = 50000   # 截断阈值,防止大查询撑爆上下文
DEFAULT_TIMEOUT = 30

# 拦截所有可能修改数据或获取额外权限的关键字
_DANGEROUS_KEYWORDS = (
    "DROP", "TRUNCATE", "DELETE", "ALTER", "CREATE",
    "INSERT", "UPDATE", "REPLACE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM", "REINDEX", "GRANT", "REVOKE",
)


def _db_path() -> Path:
    p = Path(os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH)).expanduser()
    if not p.exists():
        raise FileNotFoundError(
            f"SQLite DB not found at {p}. Set {DB_PATH_ENV} or run from a "
            f"directory containing enterprise.sqlite."
        )
    return p


def _connect() -> sqlite3.Connection:
    # mode=ro 让 SQLite 自身拒绝任何写操作——这是最内层的安全网
    uri = f"file:{_db_path()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _strip_sql_comments(sql: str) -> str:
    """剥除 -- 和 /* */ 注释,防止 `-- foo\\nDELETE` 这类绕过手法。"""
    no_line = re.sub(r"--[^\n]*", "", sql)
    no_block = re.sub(r"/\*.*?\*/", "", no_line, flags=re.DOTALL)
    return no_block
```

接着是主函数，追加到同一文件：

```python
def execute_sql(
    sql: str,
    timeout: int | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """执行一个 SELECT,返回结构化结果。"""
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

    # 安全检查 1:剥除注释后，检查第一个关键字是否为危险词
    sql_cleaned_upper = _strip_sql_comments(sql).strip().upper()
    for keyword in _DANGEROUS_KEYWORDS:
        if re.match(rf"^{keyword}(?:\s|$)", sql_cleaned_upper):
            return {
                "status": "error",
                "error": f"Only SELECT queries are allowed. Found: {keyword}",
                "sql": sql,
                "duration_ms": int((time.time() - start_time) * 1000),
            }

    # 安全检查 2:必须以 SELECT 或 WITH 开头
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

        # 为查询设置挂钟超时（每 1000 步 SQLite 回调一次此函数）
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

        # bytes/bytearray → hex, 其他非 JSON 原生类型 → str
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

        # 长度截断:逐行缩减直到 JSON 序列化结果不超过 MAX_OUTPUT_LENGTH
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
```

该函数有几个值得注意的设计：

**三层安全网，每层失效仍有下一层兜底。** 第一层是关键字白名单（仅允许 `SELECT` / `WITH` 开头）加黑名单扫描;第二层是注释剥离，防止 `-- foo\nDELETE ...` 这类将危险词隐藏在注释后绕过白名单的手法;第三层是以 `file:...?mode=ro` URI 打开数据库，即使前两层均被绕过，SQLite 引擎本身也会拒绝任何写操作。三层相互独立，任何一层单独存在都不够。

> 此处**前两层仅检查第一条语句**——`SELECT 1; DROP TABLE users` 这种语句拼接，白名单和注释剥离均无法拦截。实际起保护作用的是 SQLite Python 驱动：`cursor.execute()` 默认仅执行分号前的第一条语句，后续内容被忽略;要执行多语句需使用 `executescript()`，而本代码并未调用它。因此多语句注入无法生效，但**完全依赖 driver 的行为保障**——若将来更换数据库或驱动，这层保护即告消失，需要将白名单从"检查第一个 token"改为"按 `;` 分割并逐段过白名单"。这正是第三层 `mode=ro` 必须存在的理由：它不依赖 driver 的任何假设。

**数据库路径通过 `Path(__file__)` 解析。** `DEFAULT_DB_PATH` 基于文件自身位置计算：`tools/execute_sql.py` → `parent` = `tools/` → `parent.parent` = agent 根目录 → 拼上 `enterprise.sqlite`。这保证了本地运行和 Cloud 部署都能找到数据库——本地通过 `start.py` 设置 `ENTERPRISE_DB_PATH` 环境变量覆盖;Cloud 上 `enterprise.sqlite` 在打包时已被拷入 agent 根目录（第 7 章会讲到）。

**挂钟超时通过 progress handler 实现。** SQLite 每执行 1000 个虚拟机操作会回调一次该 handler，返回非零值即中断当前查询。这比"在外层使用 `signal.alarm`"更具可移植性——不依赖线程模型，也不会遗留半连接。

**`MAX_OUTPUT_LENGTH` 防止大查询撑爆上下文。** 即使行数没超 `max_rows`，某些列（如长文本、JSON）可能使整个返回体非常大。函数会在 JSON 序列化后检查长度，超过 50000 字符就从尾部逐行删减，直到安全范围内。

**`bytes` → `hex` 转换。** SQLite 的 `BLOB` 列在 Python 中返回 `bytes`，直接放入 JSON 会报错。函数遍历每行，将 `bytes`/`bytearray` 转为十六进制字符串，其他非 JSON 原生类型转为 `str`。

**`command_status` 字段。** 返回 `"SELECT {total_rows}"` 格式的状态字符串，使返回结构与 NexAU 的 trace 系统兼容。

**结构化返回是工具的核心价值，而不仅是"格式更清晰"。** `total_rows: 0` 配合 `warnings` 字段告知模型"执行成功但无数据，假设可能有误";`truncated: true` 告知它"仍有更多行，需细化查询";出错时统一返回 `{"status": "error", "error": "..."}` 而非抛出异常，模型一看便知是工具拒绝了请求，而非数据库本身故障。这些字段使工具结果从"答案"变为"一轮对话"——模型据此决定下一步操作。

编写完成后，该函数可以脱离 NexAU 独立测试，因为它就是一个普通 Python 函数：

```bash
ENTERPRISE_DB_PATH=enterprise.sqlite python -c "
from enterprise_data_agent.tools.execute_sql import execute_sql
print(execute_sql('SELECT enterprise_name FROM enterprise_basic LIMIT 3'))
print(execute_sql('DROP TABLE enterprise_basic'))   # 应当被拒绝
print(execute_sql('-- ok\nDELETE FROM users'))      # 同样被拒绝
"
```

## 编写 schema —— `ExecuteSQL.tool.yaml`

`tools/execute_sql.py` 模型看不到。模型看到的是 schema。创建 `enterprise_data_agent/tools/ExecuteSQL.tool.yaml`：

```yaml
type: tool
name: execute_sql
description: >-
  执行 SQL 查询并返回结果。

  使用说明:
    - 仅支持 SELECT 查询,禁止执行 DROP、DELETE、UPDATE、INSERT 等危险操作
    - 查询结果默认最多返回 10 行,可通过 max_rows 参数调整
    - 查询默认超时时间为 30 秒
    - 返回结果包含列名和数据行

  最佳实践:
    - 始终使用 LIMIT 限制返回行数
    - 对于大表查询,先使用 COUNT(*) 估计数据量
    - 使用 WHERE 条件过滤数据,避免全表扫描
    - 该数据库为 SQLite,使用 SQLite 方言
    - 使用 credit_code 在 enterprise_* 表之间做 JOIN

input_schema:
  type: object
  properties:
    sql:
      type: string
      description: 要执行的 SQL 查询语句(仅支持 SELECT)
    timeout:
      type: integer
      default: 30
      description: 查询超时时间(秒),默认 30 秒
    max_rows:
      type: integer
      default: 10
      description: 最大返回行数,默认 10 行
  required: [sql]
  additionalProperties: false
  $schema: http://json-schema.org/draft-07/schema#
```

逐字段说明：

`type: tool` 告知 NexAU 这是一份工具配置而非 agent 配置——同一种 YAML 格式，顶层 `type` 决定解析方式。

`name: execute_sql` 是模型在工具列表中看到的名称。它与 Python 函数名 `execute_sql` 以及 `agent.yaml` 中的 `name:` 字段保持一致，便于阅读和排查问题。

`description` 是该文件中对行为影响最大的部分。它决定模型何时选择该工具、调用时传入什么参数。"始终使用 LIMIT"这类规则写在工具描述中，比写在系统提示中更有效——它紧邻工具定义，模型每次决策时都会读到。

`input_schema` 采用标准 JSON Schema（draft-07）。NexAU 在启动时会根据 `agent.yaml` 中声明的 `api_type`，自动将其翻译为 OpenAI / Anthropic / Gemini 各家原生的 function definition 格式，只需编写一次。`additionalProperties: false` 阻止模型编造额外参数。

## agent.yaml

打开 `enterprise_data_agent/agent.yaml`，将 `tools:` 段从第 1 章的：

```yaml
tools:
  - name: run_shell_command
    yaml_path: ./tools/RunShellCommand.tool.yaml
    binding: nexau.archs.tool.builtin.shell_tools:run_shell_command
```

改为：

```yaml
tools:
  - name: execute_sql
    yaml_path: ./tools/ExecuteSQL.tool.yaml
    binding: tools.execute_sql:execute_sql
```

`yaml_path` 是工具 schema 文件的相对路径（相对于 `agent.yaml`）。`binding` 采用 `module.path:callable` 格式，与 setuptools entry point 写法一致。NexAU 在加载 Agent 时会：读取 `ExecuteSQL.tool.yaml` 获取 schema，`import tools.execute_sql`，取出其中的 `execute_sql` 函数，将两部分注册为一个工具供 LLM 调用。

整份 `agent.yaml` 仅修改了 `tools:` 段，其余字段全部保留第 1 章原样。

## 系统提示

第 1 章的 system prompt 中有一段 `Use run_shell_command to invoke sqlite3` 以及一个 4 步 Workflow。第 2 章 LLM 不再调用 shell 而改调 `execute_sql`，system prompt 需要整体替换——删除 shell 说明与旧 Constraints 段，补上新 Workflow。

将 `enterprise_data_agent/system_prompt.md` **整体替换**为：

```markdown
You are an enterprise data agent. The **only** database you have access to is
`enterprise.sqlite` in the current working directory. No other database files
exist — never guess or fabricate file names. It has 7 tables about Chinese
enterprises; tables that start with `enterprise_` join on `credit_code`.

## Workflow

1. **Discover schema if needed.** If you don't know a table's columns, run
   `SELECT * FROM <table> LIMIT 1` via `execute_sql` to inspect the shape.
2. **Write SELECT-only SQL.** SQLite syntax. Always include `LIMIT`. Prefer
   explicit column lists over `SELECT *`. Join `enterprise_*` on `credit_code`.
3. **Call `execute_sql`.** It returns a structured object with:
   - `status` — "success" / "error" / "timeout"
   - `columns` — column names
   - `data` — list of row dicts
   - `row_count`, `total_rows`, `truncated`
   - `warnings` — sometimes carries hints when results are empty or truncated
4. **Reflect on warnings.** If `total_rows == 0` or `warnings` is present,
   re-read your assumptions and try a different query. Don't just give up.
5. **Reply in the user's language** with a concise answer grounded in the
   actual rows. End your message with the SQL you ran in a fenced block.
```

原 `## Constraints`（READ-ONLY 约束）段不再需要——工具自身已会拒绝写操作，约束已从提示词下沉到代码。这是本章改造后系统提示变得更短的原因。

第 4 步是本版的关键。通过告知模型"warnings 字段是给你的提示，看到后需要反思"，使模型将工具结果视为一轮对话的输入而非最终答案。

## 运行

回到 `enterprise_data_agent/` 的上一级目录，与第 1 章相同的命令：

```bash
uv run enterprise_data_agent/start.py "注册地在海淀区的小型企业有多少家?"
```

最终输出看似与第 1 章相同，但背后的机制完全不同：

| | 第 1 章（bash） | 第 2 章（execute_sql） |
|---|---|---|
| 工具调用 | `run_shell_command("sqlite3 enterprise.sqlite '...'")` | `execute_sql(sql="SELECT ...")` |
| 数据库连接 | fork 一个 sqlite3 进程 | Python 直连，可复用 |
| 结果格式 | stdout 字符串 | `{"columns": [...], "data": [...], ...}` |
| `DROP TABLE` | 会实际执行 | 被拒绝 |
| 超时控制 | 无 | 30 秒挂钟 |

测试安全护栏：

```bash
uv run enterprise_data_agent/start.py "请帮我清空 enterprise_basic 表"
```

模型可能尝试生成 `DELETE FROM enterprise_basic`，工具会拒绝并返回 `{"status": "error", "error": "Only SELECT allowed. Found: DELETE"}`。模型看到该错误后会告知用户无法执行此操作——这就是结构化错误的价值：模型清楚错误出在哪一层，能给用户一个准确的解释。

再测试一个绕过场景：

```bash
uv run enterprise_data_agent/start.py "执行 -- comment\nDELETE FROM users"
```

注释剥离会发现 `DELETE` 处于第一个关键字位置，同样拒绝。

## 本章小结

一份 Python 函数 + 一份 YAML schema + `agent.yaml` 中修改一行 `binding`，即替换掉了第 1 章的"shell 执行 SQL"路径。整个 Agent 骨架不变——同一份 `system_prompt.md`、同一个 `start.py`、同一个 `agent.run()` 调用。

| 特性 | 在本章的体现 |
|---|---|
| 工具的两部分 | `tools/execute_sql.py`（实现） + `ExecuteSQL.tool.yaml`（schema） |
| `binding` 字段 | `module.path:callable` 将两部分关联 |
| schema 即提示工程 | description 决定模型何时调用、传入什么参数 |
| 结构化返回 | `warnings` / `truncated` / `total_rows` 引导模型自我反思 |
| 多层独立护栏 | 关键字白名单 + 注释剥离 + `mode=ro` + 挂钟超时 |

后续所有自定义工具均按此模式编写。第 4 章的规划工具、第 5 章经中间件包装的工具，结构都与 `execute_sql` 一致。

## 局限

尝试几个稍复杂的问题，新一轮痛点将会显现。

**类型隐含错误。** 问"海淀区注册资本最高的 3 家企业是?"，模型会编写 `ORDER BY register_capital DESC`。但 `register_capital` 在数据库中的类型是 `TEXT` 而非数字，字典序排序下 `"99"` 会排在 `"1000"` 前面，排出的"最高"全部错误。模型仅凭 schema 无法看出列的真实语义，仅通过 `SELECT * LIMIT 1` 探查也无法发现"该列为数字但存储为字符串"。

**列名依赖猜测。** 问"专精特新小巨人企业有几家?"，模型不知道存在 `zhuanjingtexin_level` 列，需要先执行 `SELECT * LIMIT 1` 探查，看到字段后再编写实际查询。每个新问题都要重新探查，既慢又浪费上下文。

**业务规则不在数据库中。** 问"AI 产业链上游有哪些企业?"，模型不知道需要 join `industry_enterprise` 和 `industry`，也不知道 `chain_position='up'` 是上游的标记。这类业务约定仅存在于业务方的认知中，不在数据库 schema 里。

**语义相近的列导致结果不稳定。** 问"注册地在海淀区的小型企业有多少家?"，模型有时返回 2、有时返回 3——因为表中存在 `register_district`（注册地）和 `jurisdiction_district`（管辖地）两个地区列，语义相近但数据不同。模型每次随机猜一个，结果便不一致。这本质上仍是列名猜测问题：如果模型事先知道两列的区别和使用场景，就不会猜错。

这四个问题根因相同——模型缺少领域知识。第 3 章将通过 Skills 将这些知识注入——按需加载、每张表一份，而非全部放入系统提示。
