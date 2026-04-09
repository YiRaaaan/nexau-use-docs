# 第 4 章 · 高级内置工具教学

> **目标**：认识 NexAU 的内置工具家族，重点学会如何将 `write_todos` 装到 Agent 上，让模型在多步任务中**先规划再执行**。
>
> **本章结束时**：面对跨多张表的复杂问题，Agent 会先列出 todo list，逐步执行并打勾，最后给出回答。
>
> **本章最重要的概念**：**内置工具的 `binding` 指向框架自带的 Python 实现，`yaml_path` 指向自行编写的 schema**——复用实现、自定义说明书，是挂载内置工具的标准方式。

## 第 3 章的痛点回顾

第 3 章末尾的跨表问题：

> "找出海淀区所有专精特新小巨人企业，列出它们的主营产品、最近一轮融资金额，并按融资金额降序排列。"

模型现在知识充足——它会按顺序读取 `enterprise_basic` / `enterprise_product` / `enterprise_financing` 三个 Skill。但接下来它会**直接尝试一次写出三表 join**，往往出问题：

- 将三个表的过滤条件混在一起，遗漏 `register_district = '海淀区'`
- join 顺序错乱，子查询位置有误
- 分了两次查询，却忘了第一次查询的中间结果用途

问题不在于知识不足，而是**缺少计划**。模型如同一个没有用草稿纸的学生在做应用题。

解决方案：给它一张草稿纸——**`write_todos` 工具**。

---

## NexAU 内置工具一览

NexAU 在 `nexau.archs.tool.builtin` 下自带一批通用工具，均可通过 `binding:` 直接挂载到 Agent 上，无需重写：

| 类别 | 工具 | 模块路径 | 用途 |
|---|---|---|---|
| **Shell** | `run_shell_command` | `nexau.archs.tool.builtin.shell_tools:run_shell_command` | 执行任意 shell 命令（第 1 章已用） |
| **文件** | `read_file` | `nexau.archs.tool.builtin.file_tools:read_file` | 按行读取文件 |
| | `write_file` | `nexau.archs.tool.builtin.file_tools:write_file` | 写入文件 |
| | `glob_tool` | `nexau.archs.tool.builtin.file_tools:glob_tool` | 按通配符查找文件 |
| | `search_file_content` | `nexau.archs.tool.builtin.file_tools:search_file_content` | grep 风格内容搜索 |
| **规划** | `write_todos` | `nexau.archs.tool.builtin.session_tools:write_todos` | 维护任务清单 |

> 实际可用的工具数量远多于上表。完整列表可通过 `python3 -c "import pkgutil, nexau.archs.tool.builtin as b; [print(m.name) for m in pkgutil.iter_modules(b.__path__)]"` 查看。

**对 enterprise data agent 而言**，文件 / 搜索类工具暂时用不到（只需查询数据库，不涉及本地文件读写）。`write_todos` 是关键。

---

## 挂载内置工具

与第 1 章的 `run_shell_command` 一样，内置工具也需要 `yaml_path` + `binding` 两部分：

```yaml
tools:
  - name: write_todos
    yaml_path: ./tools/TodoWrite.tool.yaml
    binding: nexau.archs.tool.builtin.session_tools:write_todos
```

`binding` 指向 NexAU 自带的 Python 实现，`yaml_path` 指向自行编写的 schema。这种方式的好处是：**`binding` 复用内置实现无需写代码，但模型看到的"说明书"由你自行撰写**——可以针对具体场景提供更精确的使用说明。

本章的 `write_todos` 即采用此方式：多表数据分析的规划场景与通用 todo 不完全一致，自行编写 schema 收益最大。

---

## 编写 `tools/TodoWrite.tool.yaml`

最小可用版本：

```yaml
type: tool
name: write_todos
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

  1. Call `write_todos` with one item per planned step (status `pending`).
  2. Before starting an item, call `write_todos` again with that item set to
     `in_progress`. Only one item should be `in_progress` at a time.
  3. After successfully running the query for that item, mark it
     `completed` in the next `write_todos` call.
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

> **格式与第 2 章 `execute_sql` 完全一致**——顶层 `input_schema:`，下面是标准 JSON Schema（draft-07）。NexAU 所有 `*.tool.yaml` 均使用同一个字段，不存在第二种写法。

> **关键设计**：description 中将 "When to use" 和 "When NOT to use" 写得**高度具体**，并与数据分析场景绑定（"2+ tables"、"first query failed"）。若仅写"用于追踪任务"，模型会**滥用**——对简单问题也列 todo，浪费 token。

---

## 在 `agent.yaml` 中挂载

将第 3 章的 `tools:` 块改为：

```yaml
tools:
  - name: execute_sql
    yaml_path: ./tools/ExecuteSQL.tool.yaml
    binding: enterprise_data_agent.bindings:execute_sql

  # 新增：内置 write_todos，schema 由 yaml_path 覆盖
  - name: write_todos
    yaml_path: ./tools/TodoWrite.tool.yaml
    binding: nexau.archs.tool.builtin.session_tools:write_todos
```

注意 `binding` 的模块路径：

```
nexau.archs.tool.builtin.session_tools:write_todos
└──────────────┬────────────────────┘ └────┬────┘
          Python 模块                   函数名
```

冒号左边是 Python import 路径，右边是函数名。这与第 2 章所写的 `enterprise_data_agent.bindings:execute_sql` 是**完全相同的机制**——内置工具没有特殊待遇，只是恰好位于 NexAU 自己的包中。

---

## 在 system prompt 中告知模型使用时机

仅挂载工具不够，还需在 prompt 的 Workflow 中新增一步。将第 3 章 system prompt 的 Workflow 改为：

```markdown
## Workflow

1. **Plan.** Identify which tables you need.
2. **Track tasks (when complex).** If the question requires 2+ tables OR
   multiple queries, call `write_todos` to record one task per step. Mark
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

第 2 步为新增。两个关键点：

- **"2+ tables OR multiple queries"** —— 触发条件
- **"Skip this for trivially simple, single-query questions"** —— 反触发条件，防止模型对"注册地在海淀区的小型企业有多少家"这类问题也创建 todo

---

## 执行跨表查询

```bash
uv run enterprise_data_agent/start.py "找出海淀区所有专精特新小巨人企业，列出它们的主营产品、最近一轮融资金额，并按融资金额降序排列。"
```

trace（一次完整调用中所有事件按时间顺序排成的列表）会显示模型先调用一次 `write_todos`：

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

接着调用 `execute_sql` 执行 t1，成功后再调用 `write_todos` 将 t1 标记为 `completed`、t2 标记为 `in_progress`，再执行 `execute_sql`……逐步推进。

最后一次 `execute_sql` 通常会将前面拆出的查询合并为一个 join，输出最终结果。

**未使用 `write_todos` 时**：模型直接编写大型 join，容易出错。
**引入 `write_todos` 后**：模型被迫先拆解任务，每一步都能看到中间结果，最终合并时 join 编写正确率显著提升。

> **为什么 write_todos 有效**：它本质上不是"工具"，而是一个**外化的工作记忆**。模型每次写 todos 都是在显式地表达"当前要做什么"，这种强制反思使链式思考（chain-of-thought，模型在文字中逐步展开推理过程，而非一步到位）更加稳定。

---

## 本章小结

| 概念 | 体现 |
|---|---|
| **内置工具家族** | shell / file / session / 规划，位于 `nexau.archs.tool.builtin.*` |
| **`binding` 的模块路径机制** | 与自定义工具完全一致，无特殊待遇 |
| **`yaml_path` + `binding`** | 复用内置实现，自定义场景化 schema |
| **write_todos 是外化工作记忆** | 多步任务的链式思考稳定剂 |
| **触发条件需写入 prompt** | 缺少 prompt 引导，模型不会主动使用规划工具 |

**渐进增强检查表**：

| | 第 3 章 | 第 4 章 |
|---|---|---|
| `agent.yaml` `tools:` | 1 个 | **+1 个 write_todos** |
| `tools/*.tool.yaml` | 1 个 | **+1 个 TodoWrite.tool.yaml** |
| `bindings.py` | 100 行 | **未改动**（write_todos 使用内置实现） |
| `system_prompt.md` Workflow | 6 步 | **+1 步 Track tasks** |
| Skills | 7 个 | **未改动** |

---

## 局限

执行一个**贪心**查询：

```bash
uv run enterprise_data_agent/start.py "把 enterprise_basic 表所有字段全部列出来给我看看"
```

模型大概率会编写 `SELECT * FROM enterprise_basic LIMIT 50`。50 行 × 30+ 列 × 每个值数十字 = **数十 KB 的工具返回**。

这批数据原封不动塞回 LLM 的 context，会导致两个问题：

1. **context 窗口被大幅占用**——后续对话可用预算减少
2. **token 费用上升**——为用户根本不需要看的数据买单

我们需要的是：**返回结果在进入 context 之前自动截断，超长部分用一行摘要替代**。这件事不应由每个工具各自处理（重复劳动），而应由一个**中间件**统一拦截。

第 5 章将装上 `LongToolOutputMiddleware`——生产级 enterprise data agent 的标配。

→ **第 5 章 · 生产级中间件**
