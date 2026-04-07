# 第 4 章 · 高级内置工具教学

> **目标**：认识 NexAU 的内置工具家族，重点学会怎么把 `todo_write` 装到 agent 上，让模型在多步任务里**先规划再执行**。
>
> **本章结束时**：跨多张表的复杂问题，agent 会先列一个 todo list，一步步打勾，然后再回答。
>
> **本章学的最重要的事**：**内置工具可以只用 `binding`、不写 `yaml_path`**——框架会从函数签名里自动推断 schema。这是用内置工具最快的方式。

## 第 3 章的痛点回顾

第 3 章末尾那个跨表问题：

> "找出海淀区所有专精特新小巨人企业，列出它们的主营产品、最近一轮融资金额，并按融资金额降序排列。"

模型现在知识够了——它会按顺序读 `enterprise_basic` / `enterprise_product` / `enterprise_financing` 三个 Skill。但接下来它会**直接试图一次写出三表 join**，经常出问题：

- 把三个表的过滤条件混在一起，丢掉 `register_district = '海淀区'`
- join 顺序乱，子查询位置错
- 分了两次查询，但忘了第一次查询的中间结果是干什么的

问题不是知识不够，是**没有计划**。模型像一个没用草稿纸做应用题的学生。

解决方案：给它一个草稿纸——**`todo_write` 工具**。

---

## NexAU 内置工具一览

NexAU 在 `nexau.archs.tool.builtin` 下自带一批通用工具，全都可以用 `binding:` 直接装到 agent 上，不需要你重写：

| 类别 | 工具 | 模块路径 | 用途 |
|---|---|---|---|
| **Shell** | `run_shell_command` | `nexau.archs.tool.builtin.shell_tools:run_shell_command` | 跑任意 shell（第 1 章用过） |
| **文件** | `read_file` | `nexau.archs.tool.builtin.file_tools:read_file` | 按行读取文件 |
| | `write_file` | `nexau.archs.tool.builtin.file_tools:write_file` | 写文件 |
| | `edit_file` | `nexau.archs.tool.builtin.file_tools:edit_file` | 字符串替换式编辑 |
| **搜索** | `glob_tool` | `nexau.archs.tool.builtin.search_tools:glob_tool` | 按通配符找文件 |
| | `search_file_content` | `nexau.archs.tool.builtin.search_tools:search_file_content` | grep 风格内容搜索 |
| **规划** | `todo_write` | `nexau.archs.tool.builtin.todo_write:todo_write` | 维护一个任务清单 |

> 实际可用的工具数比上面更多，可以去 NexAU 仓库 `nexau/archs/tool/builtin/` 下看完整列表。

**对 NL2SQL agent 来说**，文件 / 搜索这一栏暂时用不上（我们只查数据库，不读写本地文件）。`todo_write` 是关键。

---

## 装内置工具的两种姿势

NexAU 支持两种写法：

### 姿势 A：只写 `binding`（最快）

```yaml
tools:
  - name: todo_write
    binding: nexau.archs.tool.builtin.todo_write:todo_write
```

**没有 `yaml_path`**。框架会从 Python 函数的签名 + docstring 自动生成 schema：

- 函数参数 → tool parameters
- 参数的类型注解 → 字段类型
- docstring 第一段 → tool description

适合：**你信任内置工具的默认描述就够好了**。

### 姿势 B：自己写 `yaml_path` 覆盖 schema

```yaml
tools:
  - name: todo_write
    yaml_path: ./tools/TodoWrite.tool.yaml
    binding: nexau.archs.tool.builtin.todo_write:todo_write
```

适合：**你想给模型一个更长 / 更针对你的领域的描述**。`binding` 还是用内置实现，但模型读到的"使用说明"是你自己写的。

> 真实仓库 `nl2sql_agent/tools/TodoWrite.tool.yaml` 就是姿势 B 的例子——里面有 280+ 行非常详细的 "When to use" / "When NOT to use" / 多个 example。这是从 Claude Code 的 todo_write prompt 抄来的，对长 SQL 任务效果非常好。

本章我们用**姿势 B**，因为多表 NL2SQL 的规划场景跟通用 todo 不完全一样，自己写一份 schema 收益最大。

---

## 写 `tools/TodoWrite.tool.yaml`

最小可用版本：

```yaml
type: tool
name: todo_write
description: >-
  Maintain a structured task list for the current SQL session. Use this
  whenever the user's question requires more than one query, or touches
  more than one table. The list helps you remember what's been done and
  what's left.

  ## When to use

  1. The question requires joining or aggregating across **2+ tables**.
  2. The question has **multiple parts** ("find X, then for each X compute Y").
  3. The first query failed and you need to **iterate** with a different plan.

  ## When NOT to use

  - Single-table, single-query questions ("how many enterprises in 海淀区")
  - Trivial lookups

  ## Workflow

  1. Call `todo_write` with one item per planned step (status `pending`).
  2. Before starting an item, call `todo_write` again with that item set to
     `in_progress`. Only one item should be `in_progress` at a time.
  3. After successfully running the query for that item, mark it
     `completed` in the next `todo_write` call.
  4. When all items are `completed`, give the final answer.

input_schema:
  type: object
  properties:
    todos:
      type: array
      description: The full task list. Always send the WHOLE list, not a diff.
      items:
        type: object
        properties:
          id:
            type: string
            description: Stable id for the task (e.g. `t1`, `t2`, ...)
          content:
            type: string
            description: One-line description of the task
          status:
            type: string
            enum: [pending, in_progress, completed]
          priority:
            type: string
            enum: [low, medium, high]
        required: [id, content, status]
  required: [todos]
  additionalProperties: false
  $schema: http://json-schema.org/draft-07/schema#
```

> **格式跟第 2 章 ExecuteSQL 完全一致**——顶层 `input_schema:`，下面是标准 JSON Schema(draft-07)。NexAU 所有 `*.tool.yaml` 都用这一个统一字段，不存在第二种写法。

> **关键设计**：description 里把 "When to use" 和 "When NOT to use" 写得**非常具体**，并且和 NL2SQL 场景绑定（"2+ tables"、"first query failed"）。如果只写"用来追踪任务"，模型会**乱用**——简单问题也要列 todo，浪费 tokens。

仓库里 `nl2sql_agent/tools/TodoWrite.tool.yaml` 是这个 schema 的"豪华版"，可以直接复制。

---

## 在 `agent.yaml` 里挂上

把第 3 章的 `tools:` 块改成：

```yaml
tools:
  - name: execute_sql
    yaml_path: ./tools/ExecuteSQL.tool.yaml
    binding: nl2sql_agent.bindings:execute_sql

  # 新增：内置 todo_write，自带 schema 被我们用 yaml_path 覆盖
  - name: todo_write
    yaml_path: ./tools/TodoWrite.tool.yaml
    binding: nexau.archs.tool.builtin.todo_write:todo_write
```

注意 `binding` 的模块路径：

```
nexau.archs.tool.builtin.todo_write:todo_write
└──────────┬─────────────────────┘ └──┬──┘
       Python 模块               函数名
```

冒号左边是 Python import 路径，右边是函数名。这跟我们第 2 章写的 `nl2sql_agent.bindings:execute_sql` 是**完全同一个机制**——内置工具不是特殊待遇，只是恰好住在 NexAU 自己的包里。

> **模块名为什么有的带 `_tools` 有的不带?** `shell_tools` / `file_tools` / `search_tools` 这些模块里各塞了一组相关函数，所以用复数 `_tools`;`todo_write` 因为只放了一个函数，模块名直接跟函数同名。这是历史原因导致的不规律，不影响使用——抄路径的时候按上面那张表来就行，记不住就去 NexAU 仓库 `nexau/archs/tool/builtin/` 下翻。

---

## 在 system prompt 里告诉模型什么时候用

光装上工具不够，还得在 prompt 的 Workflow 里加一步。把第 3 章 system prompt 的 Workflow 改成：

```markdown
## Workflow

1. **Plan.** Identify which tables you need.
2. **Track tasks (when complex).** If the question requires 2+ tables OR
   multiple queries, call `todo_write` to record one task per step. Mark
   each `in_progress` before working on it and `completed` after the query
   succeeds. Skip this for trivially simple, single-query questions.
3. **Read Skills.** For every table you'll touch, read its Skill first.
4. **Write the SQL.** SQLite syntax. `LIMIT`. Explicit columns.
5. **Execute.** Call `execute_sql`.
6. **Reflect.** If `total_rows == 0` or `warnings` is set, re-read the
   Skill and try a different query. Update the todo list accordingly.
7. **Answer** in the user's language with a concise answer grounded in
   the actual rows. End with the SQL in a fenced block.
```

第 2 步是新加的。两个关键词：

- **"2+ tables OR multiple queries"** —— 触发条件
- **"Skip this for trivially simple, single-query questions"** —— 反触发条件，防止它对 "海淀区有多少家小型企业" 这种问题也列 todo

---

## 跑那个跨表问题

```bash
dotenv run uv run nl2sql_agent/start.py "找出海淀区所有专精特新小巨人企业，列出它们的主营产品、最近一轮融资金额，并按融资金额降序排列。"
```

trace 就是一次完整调用里所有事件按时间顺序排成的列表。用 `dotenv run uv run nl2sql_agent/start.py` 跑的时候，trace 直接打在 stdout 上;如果你用 NexAU 自带的 CLI `./run-agent nl2sql_agent/agent.yaml`,trace 会更结构化、还能折叠工具调用。观察 trace，你应该看到模型先调一次 `todo_write`:

```json
{
  "todos": [
    {"id": "t1", "content": "查海淀区专精特新小巨人企业 (enterprise_basic)", "status": "in_progress"},
    {"id": "t2", "content": "用 credit_code join enterprise_product 拿主营产品", "status": "pending"},
    {"id": "t3", "content": "用 credit_code join enterprise_financing 拿最近一轮融资金额", "status": "pending"},
    {"id": "t4", "content": "按融资金额降序排，输出最终结果", "status": "pending"}
  ]
}
```

然后调 `execute_sql` 跑 t1，跑成功后再调 `todo_write` 把 t1 标 `completed`、t2 标 `in_progress`，再 `execute_sql` ……一步一步推进。

最后一次 `execute_sql` 可能就是把前面拆出来的查询合并成一个 join，输出最终结果。

**没有 `todo_write` 之前**：模型一上来就写大 join，写错。
**有了 `todo_write` 之后**：模型被迫先把任务拆开，每一步都看到了中间结果，最后合并的时候 join 写对的概率显著提升。

> **为什么 todo_write 有用**:本质上它不是"工具"，是一个**外化的工作记忆**。模型每次写 todos 都是在自言自语"我现在要做什么"，这种强制反思让链式思考(chain-of-thought，模型一步步在文字里把推理过程"演"出来，而不是脑内一步到位)更稳。

---

## 你刚才学到了什么

| 概念 | 你看到的 |
|---|---|
| **内置工具家族** | shell / file / search / 规划，住在 `nexau.archs.tool.builtin.*` |
| **`binding` 的模块路径机制** | 跟自定义工具一模一样，没有特殊待遇 |
| **只写 binding 的快捷写法** | 框架从函数签名自动生成 schema |
| **写自己的 yaml_path 覆盖 schema** | 给内置工具换一份场景化描述 |
| **todo_write 是外化工作记忆** | 多步任务的链式思考稳定剂 |
| **触发条件要写在 prompt 里** | 没有 prompt 引导，模型不会主动用规划工具 |

**渐进增强检查表**：

| | 第 3 章 | 第 4 章 |
|---|---|---|
| `agent.yaml` `tools:` | 1 个 | **+1 个 todo_write** |
| `tools/*.tool.yaml` | 1 个 | **+1 个 TodoWrite.tool.yaml** |
| `bindings.py` | 100 行 | **未改动**（todo_write 用内置实现） |
| `system_prompt.md` Workflow | 6 步 | **+1 步 Track tasks** |
| Skills | 7 个 | **未改动** |

---

## 局限

跑一个**贪心**查询：

```bash
dotenv run uv run nl2sql_agent/start.py "把 enterprise_basic 表所有字段全部列出来给我看看"
```

模型大概率会写 `SELECT * FROM enterprise_basic LIMIT 50`。50 行 ✕ 30+ 列 ✕ 每个值动辄几十字 = **几十 KB 的工具返回**。

这一坨数据被原封不动塞回 LLM 的 context，会发生两件事：

1. **context 窗口被吃掉一大块**——剩下的对话能用的预算变小
2. **token 账单上升**——你为一坨用户根本不需要看的数据付钱

我们要的是：**返回结果在塞进 context 之前自动截断头尾，超长部分用一行摘要替代**。这件事不应该由每个工具自己做（重复劳动），而应该由一个**中间件**统一拦截。

第 5 章我们装上 `LongToolOutputMiddleware`——一个生产级 NL2SQL agent 的标配。

→ **第 5 章 · 生产级中间件**
