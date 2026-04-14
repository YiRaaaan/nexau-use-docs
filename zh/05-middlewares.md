# 第 5 章 · 生产级中间件

> **目标**：启用 `LongToolOutputMiddleware`，使任何"贪心"查询都不会撑爆 context。
>
> **本章结束时**：`SELECT * FROM enterprise_basic LIMIT 50` 这类查询返回的数十 KB 数据，会被自动截为头 30 行 + 尾 10 行 + 一行省略提示，再传入 LLM。
>
> **本章最重要的概念**：**Middleware 是 NexAU 的横切关注点机制**——不属于任何具体工具、但每个工具都要经过的逻辑（截断、压缩、日志、tracing），统一在此处处理。

## 第 4 章的痛点回顾

第 4 章末尾的贪心查询：

```bash
uv run enterprise_data_agent/start.py "把 enterprise_basic 表所有字段全部列出来给我看看"
```

模型编写 `SELECT * FROM enterprise_basic LIMIT 50`，工具返回的 `data` 字段是一个 50 × 30 的二维数组，每个 cell 包含数十字中文。整个返回 JSON 约 30–60 KB。

将 30 KB 原封不动传回 LLM 的 context，会导致：

1. context 配额被大幅占用（10–20 K tokens）
2. 模型完全不需要看完所有行即可总结，但已为此付费
3. 后续对话可用预算减少，多轮时容易截断

我们需要的是：**返回结果在加入 message history 之前，超长部分自动截断**。但这件事不应写在 `execute_sql` 中——下一个工具同样会面临此问题。它属于**横切关注点**（cross-cutting concern，指不属于任何具体业务、但所有业务都需经过的逻辑，如日志、限流、超长截断），应由中间件统一处理。

---

## 什么是 Middleware

Middleware 是一段**包裹在工具调用外层**的代码。每次模型调用任何工具时：

```
LLM → [middleware 1] → [middleware 2] → tool → [middleware 2] → [middleware 1] → LLM
```

中间件可以：

- 在工具被调用**之前**检查 / 修改参数（input hook）
- 在工具返回**之后**修改结果再交给 LLM（output hook）
- 决定**完全不调用**工具（短路）

NexAU 内置几个常用中间件：

| 中间件 | 模块路径 | 作用 |
|---|---|---|
| `LongToolOutputMiddleware` | `nexau.archs.main_sub.execution.middleware.long_tool_output:LongToolOutputMiddleware` | 截断超长工具返回 |
| `ContextCompactionMiddleware` | `nexau.archs.main_sub.execution.middleware.context_compaction:ContextCompactionMiddleware` | 接近 context 上限时自动压缩历史消息 |

本章重点启用第一个。

---

## 在 `agent.yaml` 中挂载 `LongToolOutputMiddleware`

**为什么用它？** 上述 30 KB 问题，根源在于"工具返回什么，LLM 就看到什么"——没有任何缓冲层。`LongToolOutputMiddleware` 正是那个缓冲层：它在工具执行完毕、结果写入 message history **之前**拦截输出，若总字符数超过阈值就截取头部若干行 + 尾部若干行，中间替换为一行省略提示，然后再交给 LLM。工具自身拿到的仍是完整结果，只有 LLM 看到的那份被压缩——这是"横切"的精髓：业务逻辑不感知截断的存在。

在第 4 章的 `agent.yaml` 末尾添加 `middlewares:` 块。注意中间件使用 `import:` 字段，工具使用 `binding:`，两者作用相同——均为 `module.path:ClassOrFunction` 格式，告知 NexAU 从何处导入 Python 对象。名称不同仅为历史原因：tool 通常绑定到函数（binding），middleware 通常是类（import），写法和效果对应。

```yaml
type: agent
name: enterprise_data_agent
# ... 前面的所有内容保持不变 ...

middlewares:
  - import: nexau.archs.main_sub.execution.middleware.long_tool_output:LongToolOutputMiddleware
    params:
      max_output_chars: 8000
      head_lines: 30
      tail_lines: 10
      head_chars: 4000
      tail_chars: 2000
```

参数说明：

| 参数 | 含义 | 取值 |
|---|---|---|
| `max_output_chars` | 工具返回总字符数低于此值时**直接放行** | `8000` |
| `head_lines` | 超过阈值后保留前 N 行 | `30` |
| `tail_lines` | 保留后 N 行 | `10` |
| `head_chars` | 头部最多保留 N 字符（防单行过长的情况） | `4000` |
| `tail_chars` | 尾部最多保留 N 字符 | `2000` |

中间部分被一行摘要替换，例如：

```
... [truncated 27 lines / 14_823 chars] ...
```

> **数值选取依据**：8000 字符 ≈ 2 K tokens，对数据查询工具而言**足以看清一个完整结果**（30 行 × 几列），同时不会让一次贪心 `SELECT *` 占满 context。这是经验值，可根据模型和预算自行调整。

---

## 执行贪心查询

```bash
uv run enterprise_data_agent/start.py "把 enterprise_basic 表所有字段全部列出来给我看看"
```

观察 trace：模型仍会调用 `execute_sql(sql="SELECT * FROM enterprise_basic LIMIT 50")`，工具实际**也返回了**完整的 50 行——但传回 LLM 的那一份**已经过截断处理**：

```
{
  "status": "success",
  "columns": [...],
  "data": [
    [1, "MOCKCREDIT0000000001", "测试企业_1", ...],
    [2, "MOCKCREDIT0000000002", "测试企业_2", ...],
    ... 30 行 ...
... [truncated 17 lines / 12_400 chars] ...
    [48, "MOCKCREDIT0000000048", ...],
    [49, "MOCKCREDIT0000000049", ...],
    [50, "MOCKCREDIT0000000050", ...]
  ],
  "row_count": 50,
  "total_rows": 50
}
```

模型看到这份数据足以告知用户："该表大致结构如此，前几行为 X、Y、Z，共 50 行"。**模型并不知晓中间被截断过**——它所见即工具返回。

**关键点**：截断仅发生在**进入 message history 的那一份**上。`execute_sql` 自身获取的、`tools/execute_sql.py` 内部使用的，都是完整结果。中间件只修改 LLM 看到的那一份。

---

## 其他值得了解的中间件

`LongToolOutputMiddleware` 是效果最直观的一个，但生产级 Agent 通常还会叠加其他中间件：

### `ContextCompactionMiddleware` — 历史消息压缩

长对话运行久后，message history 会持续增长。该中间件在接近 context 上限时**自动总结早期消息**，将"前 30 轮的工具调用 + 回复"压缩为一段数百字的摘要，然后继续。

对数据分析并非必需，但若用户在同一 session 中连续提问数十个问题，**未启用该中间件将导致 context 溢出**。

```yaml
middlewares:
  - import: nexau.archs.main_sub.execution.middleware.long_tool_output:LongToolOutputMiddleware
    params:
      max_output_chars: 8000
      # ...
  - import: nexau.archs.main_sub.execution.middleware.context_compaction:ContextCompactionMiddleware
    params:
      threshold: 0.8             # context 使用达 80% 时触发
      keep_iterations: 6        # 始终保留最近 6 轮工具调用原文
```

### Tracing — Langfuse / OpenTelemetry

Tracing（链路追踪：将一次请求中发生的所有事件按时间顺序串联，便于事后回放）。NexAU 支持将每轮 LLM 调用 + 工具调用挂到 Langfuse（一个开源的 LLM 可观测平台，专用于查看 Agent trace）。配置通常在 agent.yaml 同级的全局配置中，不严格属于 middleware 章节。**值得一提**：上线企业数据分析 Agent 后，Langfuse trace 是**唯一**能查明"为什么某个用户的查询回答错误"的工具——它将每个 Skill 是否被读取、每条 SQL 如何生成、每次工具返回的内容，全部串成一条可点击的时间线。

> 如需接入 Langfuse，请参考 NexAU 文档的 tracing 章节，本教程不做展开。

### 自定义 middleware

Middleware 就是一个 Python 类，实现 `before_tool_call` / `after_tool_call` 等钩子。例如，可以编写一个 `RedactCreditCodeMiddleware`，在工具返回中自动将 `credit_code` 字段脱敏为 `***`。机制与编写工具同样简单。本教程到此为止，留待自行探索。

---

## 本章小结

| 概念 | 体现 |
|---|---|
| **Middleware = 横切关注点** | 截断 / 压缩 / 日志 / tracing 均在此处理 |
| **`import:` + `params:`** | YAML 中挂载中间件的标准格式 |
| **`LongToolOutputMiddleware`** | 数据分析 Agent 的标配，防 `SELECT *` 撑爆 context |
| **截断仅影响 LLM 看到的那一份** | 工具自身获取的仍是完整结果 |
| **数值应根据模型 / 预算调整** | 8000 chars / 30 head / 10 tail 为经验值 |

**渐进增强检查表**：

| | 第 4 章 | 第 5 章 |
|---|---|---|
| `max_iterations` | 50 | **未改动** |
| `agent.yaml` | tools + skills | **+ middlewares 7 行** |
| `tools/execute_sql.py` | ~270 行 | **未改动** |
| `tools/*.tool.yaml` | 2 个 | **未改动** |
| `skills/*/SKILL.md` | 7 个 | **未改动** |
| `system_prompt.md` | 7 步 | **未改动** |

第 5 章仅增加 7 行 YAML。**无任何代码改动**，但 Agent 的"耐用度"提升了一个台阶——它不再会因一次贪心查询而崩溃。

---

## 至此 Agent 已达生产级

回顾已完成的工作：

```
enterprise_data_agent/
├── agent.yaml             # ~50 行：llm/tools/skills/middlewares
├── system_prompt.md       # 7 步 workflow
├── tools/execute_sql.py   # ~270 行：execute_sql + 安全护栏
├── tools/
│   ├── ExecuteSQL.tool.yaml
│   └── TodoWrite.tool.yaml
├── skills/
│   ├── enterprise_basic/SKILL.md
│   ├── enterprise_contact/SKILL.md
│   ├── enterprise_financing/SKILL.md
│   ├── enterprise_product/SKILL.md
│   ├── industry/SKILL.md
│   ├── industry_enterprise/SKILL.md
│   └── users/SKILL.md
├── start.py               # 简单的 CLI 入口
└── enterprise.sqlite
```

它已具备：

- **结构化、安全的工具**（第 2 章）
- **领域知识按需加载**（第 3 章）
- **多步任务规划**（第 4 章）
- **超长输出截断**（第 5 章）

剩下一件事：当前使用的是 `openai_chat_completion` API。若要切换到其他 Provider（Anthropic / Gemini / OpenAI Responses API），需要修改什么？答案：**两行 YAML**。

→ **第 6 章 · 加一个做 PPT 的技能**
