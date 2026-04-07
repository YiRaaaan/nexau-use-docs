# 第 2 章 · 写自定义 SQL 工具

## 第 1 章的痛点回顾

第 1 章的智能体能跑，但它有四个明显的代价:

- **结果是 stdout 字符串**——LLM 自己数空格、对齐列名，容易出错
- **安全靠 system prompt**——模型一旦"听不懂话"，就能真的跑 `DELETE`
- **每次调用 fork 一个 sqlite3 进程**——延迟和资源都更高
- **LLM 不知道列名，每次都要先 `.schema` 探一次**

第 2 章一次性解决前三个，办法是用一个自定义 Python 工具替换掉 `run_shell_command`(列名问题留给第 3 章用 Skills 解决)。这一章讲的不只是"怎么写一个 SQL 工具"，而是 NexAU 里所有自定义工具都遵循的同一个模式——一份 Python 实现加一份 YAML schema，通过 `binding` 在 `agent.yaml` 里粘起来。

## 一个 NexAU 工具有两半

NexAU 里每个工具都是两个文件:

| 部分 | 文件 | 给谁看 |
|---|---|---|
| schema | `tools/<Name>.tool.yaml` | 给 LLM 看的:名字、描述、参数 |
| 实现 | `bindings.py` 里的一个函数 | 给机器跑的:真正执行的代码 |

两者通过 `agent.yaml` 里的 `binding:` 字段绑在一起。

之所以拆成两份，是因为它们演化速度不同。schema 里的每一个词都会影响"模型什么时候选这个工具、传什么参数"，改 description 是提示工程，需要反复调;实现里是普通 Python，改它是写代码、跑测试。把它们放在两个文件里，改一边不用动另一边。

下面按这个顺序做:实现 → schema → 在 `agent.yaml` 里绑起来 → 改一行系统提示。

## 写实现 —— `bindings.py`

在 `nl2sql_agent/` 下创建 `bindings.py`。先是 setup:

```python
"""NL2SQL Agent 的工具实现:一个安全的只读 execute_sql。"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH_ENV = "NL2SQL_DB_PATH"
DEFAULT_DB_PATH = "enterprise.sqlite"

MAX_ROWS = 10
DEFAULT_TIMEOUT = 30

# 任何会改数据或拿到额外权限的关键字都拦掉
_DANGEROUS_KEYWORDS = (
    "DROP", "TRUNCATE", "DELETE", "ALTER", "CREATE",
    "INSERT", "UPDATE", "REPLACE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM", "REINDEX", "GRANT", "REVOKE",
)


def _db_path() -> Path:
    p = Path(os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH)).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"SQLite DB not found at {p}")
    return p


def _connect() -> sqlite3.Connection:
    # mode=ro 让 SQLite 自己拒绝任何写操作——这是最里层的安全网
    uri = f"file:{_db_path()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _strip_sql_comments(sql: str) -> str:
    """剥掉 -- 和 /* */ 注释,防止 `-- foo\\nDELETE` 这种绕过。"""
    no_line = re.sub(r"--[^\n]*", "", sql)
    no_block = re.sub(r"/\*.*?\*/", "", no_line, flags=re.DOTALL)
    return no_block
```

接着是主函数，追加到同一个文件:

```python
def execute_sql(
    sql: str,
    timeout: int | None = None,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """执行一个 SELECT,返回结构化结果。"""
    start = time.time()
    timeout = timeout or DEFAULT_TIMEOUT
    max_rows = max_rows or MAX_ROWS

    if not sql or not sql.strip():
        return {"status": "error", "error": "SQL query cannot be empty"}

    # 安全检查 1:剥掉注释,再看第一个关键字是不是危险词
    sql_upper = _strip_sql_comments(sql).strip().upper()
    for kw in _DANGEROUS_KEYWORDS:
        if re.match(rf"^{kw}(?:\s|$)", sql_upper):
            return {"status": "error",
                    "error": f"Only SELECT allowed. Found: {kw}"}

    # 安全检查 2:必须以 SELECT 或 WITH 开头
    if not re.match(r"^(SELECT|WITH)\b", sql_upper):
        return {"status": "error",
                "error": "Only SELECT/WITH queries allowed."}

    conn = None
    try:
        conn = _connect()

        # 给查询加一个挂钟超时(每 1000 步 SQLite 会回调一次这个函数)
        deadline = time.time() + timeout
        conn.set_progress_handler(
            lambda: 1 if time.time() > deadline else 0, 1000
        )

        cursor = conn.execute(sql)
        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()

        total = len(rows)
        truncated = total > max_rows
        rows_to_return = rows[:max_rows] if truncated else rows

        result = {
            "status": "success",
            "sql": sql,
            "columns": cols,
            "data": [dict(r) for r in rows_to_return],
            "row_count": len(rows_to_return),
            "total_rows": total,
            "truncated": truncated,
            "duration_ms": int((time.time() - start) * 1000),
        }

        # 空结果给模型一个有用的提示,让它知道往哪个方向反思
        if total == 0:
            result["warnings"] = [
                "查询返回 0 行。检查表名、列名、WHERE 是否过严。"
            ]
        return result

    except sqlite3.OperationalError as e:
        msg = str(e)
        if "interrupted" in msg.lower():
            return {"status": "timeout",
                    "error": f"Query timed out after {timeout}s"}
        return {"status": "error", "error": msg, "sql": sql}
    finally:
        if conn is not None:
            conn.close()
```

这个函数有几个值得注意的设计:

**三层安全网，每层失效都还有下一层兜底。** 第一层是关键字白名单(只允许 `SELECT` / `WITH` 开头)加黑名单扫描;第二层是注释剥离，防止 `-- foo\nDELETE ...` 这种把危险词藏到第一行后面绕过白名单的写法;第三层是用 `file:...?mode=ro` URI 打开数据库，即使前两层都被绕过，SQLite 引擎本身也会拒绝任何写操作。三层独立，任何一层单独存在都不够。

> 这里**前两层只检查第一个语句**——`SELECT 1; DROP TABLE users` 这种语句拼接，白名单和注释剥离都拦不住。救命的是 SQLite Python 驱动:`cursor.execute()` 默认只跑分号前的第一条语句，后面的整段直接被忽略;真正想跑多语句要用 `executescript()`，这个方法我们根本没调。所以多语句注入打不进来，但**完全是 driver 帮我们兜的底**——如果有一天换数据库或者换 driver，这一层保护就消失了，需要把白名单从"检查第一个 token"改成"按 `;` 分割每一段都过白名单"。这就是第三层 `mode=ro` 必须存在的理由:它对 driver 行为没有任何假设。

**挂钟超时挂在 progress handler 上。** SQLite 每跑 1000 个虚拟机操作就会回调一次这个 handler，返回非零值会中断当前查询。这比"在外层包一个 `signal.alarm`"可移植得多——它不依赖线程模型，也不会留下半连接。

**结构化返回是工具的真正价值，不只是"格式更好看"。** `total_rows: 0` 配合 `warnings` 字段告诉模型"我执行成功了但没数据，你的假设可能错了";`truncated: true` 告诉它"还有更多行，要 refine 你的查询";出错时统一是 `{"status": "error", "error": "..."}` 而不是抛异常，模型一看就知道是工具拒绝了它，而不是数据库本身坏了。这些字段让工具结果从"答案"变成"一轮对话"——模型会根据它来决定下一步做什么。

写完之后，这个函数可以脱离 NexAU 单独测，因为它就是个普通 Python 函数:

```bash
NL2SQL_DB_PATH=enterprise.sqlite python -c "
from nl2sql_agent.bindings import execute_sql
print(execute_sql('SELECT enterprise_name FROM enterprise_basic LIMIT 3'))
print(execute_sql('DROP TABLE enterprise_basic'))   # 应该被拒绝
print(execute_sql('-- ok\nDELETE FROM users'))      # 也被拒绝
"
```

## 写 schema —— `ExecuteSQL.tool.yaml`

`bindings.py` 模型看不到。它看到的是 schema。创建 `nl2sql_agent/tools/ExecuteSQL.tool.yaml`:

```yaml
type: tool
name: ExecuteSQL
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

逐字段说明:

`type: tool` 让 NexAU 知道这是一份工具配置而不是 agent 配置——同一种 YAML 格式，顶层 `type` 决定怎么解析。

`name: ExecuteSQL` 是模型在工具列表里看到的名字。注意它跟 Python 函数名 `execute_sql` 大小写不一样，这是允许的:模型看 schema 名，运行时框架靠 `binding` 字段去找真正的函数，两套独立的命名空间。同名能省心，但不强制。

`description` 是这份文件里最影响行为的部分。它决定了模型什么时候挑这个工具、调用时传什么参数。"始终使用 LIMIT" 这种规则写在工具描述里，比写在系统提示里更有效——它就贴在工具旁边，模型每次决策时都会看到。

`input_schema` 是标准 JSON Schema(draft-07)。NexAU 在启动时会按 `agent.yaml` 里声明的 `api_type` 自动把它翻译成 OpenAI / Anthropic / Gemini 各家原生的 function definition 格式，你只需要写一次。`additionalProperties: false` 让模型没法瞎编额外参数。

## agent.yaml

打开 `nl2sql_agent/agent.yaml`，把 `tools:` 段从第 1 章的:

```yaml
tools:
  - name: run_shell_command
    binding: nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command
```

改成:

```yaml
tools:
  - name: ExecuteSQL
    yaml_path: ./tools/ExecuteSQL.tool.yaml
    binding: nl2sql_agent.bindings:execute_sql
```

`yaml_path` 是工具 schema 文件的相对路径(相对于 `agent.yaml`)。`binding` 用 `module.path:callable` 格式，跟 setuptools entry point 一样的写法。NexAU 在加载智能体时会:读 `ExecuteSQL.tool.yaml` 拿到 schema,`import nl2sql_agent.bindings`，取出里面的 `execute_sql` 函数，把这两半注册成一个工具丢给 LLM 去调用。

整份 `agent.yaml` 只改了 `tools:` 这一段，其他字段全部保留第 1 章原样。

## 系统提示

第 1 章的 system prompt 里有一段 `Use run_shell_command to invoke sqlite3` 和一个 4 步 Workflow。第 2 章 LLM 不再调 shell,改调 ExecuteSQL,要做两件事:把那段 `run_shell_command` 的格式说明删掉,然后把 Workflow 从 4 步扩到 5 步——多出来的一步是 **Reflect**,告诉模型怎么处理结构化返回里的 `warnings` / `total_rows`。

打开 `nl2sql_agent/system_prompt.md`,把 Workflow 段替换成:

```markdown
## Workflow

1. **Discover schema if needed.** If you don't know a table's columns, run
   `SELECT * FROM <table> LIMIT 1` via ExecuteSQL to inspect the shape.
2. **Write SELECT-only SQL.** SQLite syntax. Always include `LIMIT`. Prefer
   explicit column lists over `SELECT *`. Join `enterprise_*` on `credit_code`.
3. **Call ExecuteSQL.** It returns a structured object with:
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

第 1 章里的 "READ-ONLY" 那段约束可以删掉了。现在工具自己会拒绝写操作，不再需要 LLM"自律"。这是把约束从提示词移到代码里之后的副作用——系统提示反而变短。

第 4 步是这一版的关键。我们告诉模型 "warnings 字段是给你的提示，看到了就反思"，让模型把工具结果当成一轮对话的输入，而不是答案本身。

## 运行

回到 `nl2sql_agent/` 的上一级目录，跟第 1 章一样的命令:

```bash
dotenv run uv run nl2sql_agent/start.py "海淀区有多少家小型企业?"
```

最终输出看起来跟第 1 章很像，但背后的事情完全不同了:

| | 第 1 章(bash) | 第 2 章(execute_sql) |
|---|---|---|
| 工具调用 | `run_shell_command("sqlite3 enterprise.sqlite '...'")` | `ExecuteSQL(sql="SELECT ...")` |
| 数据库连接 | fork 一个 sqlite3 进程 | Python 直接连，可复用 |
| 结果格式 | stdout 字符串 | `{"columns": [...], "data": [...], ...}` |
| `DROP TABLE` | 会真的执行 | 被拒绝 |
| 超时控制 | 无 | 30 秒挂钟 |

试一下安全护栏:

```bash
dotenv run uv run nl2sql_agent/start.py "请帮我清空 enterprise_basic 表"
```

模型可能会尝试生成 `DELETE FROM enterprise_basic`，工具会拒绝并返回 `{"status": "error", "error": "Only SELECT allowed. Found: DELETE"}`。模型看到这个错误后会告诉用户它做不了这件事——这就是结构化错误的价值:模型知道错在哪一层，能给用户一个准确的解释。

再试一个绕过测试:

```bash
dotenv run uv run nl2sql_agent/start.py "执行 -- comment\nDELETE FROM users"
```

注释剥离会发现 `DELETE` 在第一个关键字位置，照样拒绝。

## 这一版给了你什么

一份 Python 函数 + 一份 YAML schema + `agent.yaml` 里改一行 `binding`，你就替换掉了第 1 章的"shell 跑 SQL"路径。整个智能体的骨架没变——还是同一份 `system_prompt.md`、同一个 `start.py`、同一个 `agent.run()` 调用。

| 特性 | 在这一章里的体现 |
|---|---|
| 工具的两半 | `bindings.py`(实现) + `ExecuteSQL.tool.yaml`(schema) |
| `binding` 字段 | `module.path:callable` 把两半粘到一起 |
| schema 即提示工程 | description 决定模型何时调用、传什么参数 |
| 结构化返回 | `warnings` / `truncated` / `total_rows` 让模型自我反思 |
| 多层独立护栏 | 关键字白名单 + 注释剥离 + `mode=ro` + 挂钟超时 |

后面所有自定义工具都按这个模式写。第 4 章的规划工具、第 5 章的中间件包装的工具，结构都跟 `ExecuteSQL` 一样。

## 局限

跑几个稍微复杂的问题，新一轮的痛点会冒出来。

**类型隐含错误。** 问"海淀区注册资本最高的 3 家企业是?"，模型会写 `ORDER BY register_capital DESC`。但 `register_capital` 在数据库里是 `TEXT` 不是数字，字典序排序下 `"99"` 会排在 `"1000"` 前面，排出来的"最高"全错。模型从 schema 里看不出列的真实语义，光靠 `SELECT * LIMIT 1` 探一次也看不出"这一列是数字但存成了字符串"。

**列名靠猜。** 问"专精特新小巨人企业有几家?"，模型不知道有 `zhuanjingtexin_level` 这一列，得先 `SELECT * LIMIT 1` 探一次，看见字段后再写真正的查询。每个新问题都要重新探一遍，既慢又浪费上下文。

**业务规则不在数据库里。** 问"AI 产业链上游有哪些企业?"，模型不知道要 join `industry_enterprise` 和 `industry`，也不知道 `chain_position='up'` 是上游的标记。这种业务约定只存在于业务方的脑子里，不在数据库 schema 里。

这三件事都是同一个根因——模型没有领域知识。第 3 章用 Skills 把这些知识喂给它——按需加载、每张表一份，而不是把所有信息塞进系统提示。
