# 第 5 章 · 生产级中间件

> **目标**：装上 `LongToolOutputMiddleware`，让任何"贪心"查询都不会撑爆 context。
>
> **本章结束时**：`SELECT * FROM enterprise_basic LIMIT 50` 这种查询返回的几十 KB 数据，会被自动截成头 30 行 + 尾 10 行 + 一行省略提示，再塞进 LLM。
>
> **本章学的最重要的事**：**Middleware 是 NexAU 的横切关注点机制**——一些不属于任何具体工具、但每个工具都要走一遍的逻辑（截断、压缩、日志、tracing），统一在这里处理。

## 第 4 章的痛点回顾

第 4 章末尾那个贪心查询：

```bash
dotenv run uv run nl2sql_agent/start.py "把 enterprise_basic 表所有字段全部列出来给我看看"
```

模型写出 `SELECT * FROM enterprise_basic LIMIT 50`，工具返回的 `data` 字段是一个 50 ✕ 30 的二维数组，每个 cell 又有几十字的中文。整个返回 JSON 在 30–60 KB 之间。

把 30 KB 原封不动塞回 LLM 的 context，会发生：

1. context 配额被吃掉一大块（10–20 K tokens）
2. 模型根本不需要看完所有行就能总结，但你已经为此付费
3. 后续对话剩下的预算变小，多轮容易截断

我们想要:**返回结果在被加进 message history 之前，超长部分自动截断**。但这件事不应该写在 `execute_sql` 里——下一个工具一样会有这个问题。它属于**横切关注点**(cross-cutting concern，指那种"不属于任何具体业务，但所有业务都要走一遍"的逻辑，比如日志、限流、超长截断)，应该被中间件统一处理。

---

## 什么是 Middleware

Middleware 是一段**包在工具调用外面**的代码。每次模型调用任何一个工具：

```
LLM → [middleware 1] → [middleware 2] → tool → [middleware 2] → [middleware 1] → LLM
```

中间件可以：

- 在工具被调用**之前**检查/修改参数（input hook）
- 在工具返回**之后**修改结果再交给 LLM（output hook）
- 决定**根本不调用**工具（短路）

NexAU 内置几个常用的：

| 中间件 | 模块路径 | 作用 |
|---|---|---|
| `LongToolOutputMiddleware` | `nexau.archs.main_sub.execution.middleware.long_tool_output:LongToolOutputMiddleware` | 截断超长工具返回 |
| `ContextCompactionMiddleware` | `nexau.archs.main_sub.execution.middleware.context_compaction:ContextCompactionMiddleware` | 接近 context 上限时自动压缩历史消息 |
| `LoggingMiddleware` | `nexau.archs.main_sub.execution.middleware.logging:LoggingMiddleware` | 把每次工具调用打到日志 |

> 实际可用列表见 NexAU 仓库 `nexau/archs/main_sub/execution/middleware/`。

本章重点装第一个。

---

## 在 `agent.yaml` 里挂上 `LongToolOutputMiddleware`

在第 4 章的 `agent.yaml` 末尾加一个 `middlewares:` 块。注意中间件用的是 `import:` 字段，工具用的是 `binding:`，两者的作用其实是一样的——都是 `module.path:ClassOrFunction` 格式，告诉 NexAU 去哪儿 import 一个 Python 对象。名字不一样只是历史原因:tool 通常绑到一个函数(binding),middleware 通常是一个类(import)，两边的写法和效果是对应的。

```yaml
type: agent
name: nl2sql_agent
# ... 前面的所有内容都不变 ...

middlewares:
  - import: nexau.archs.main_sub.execution.middleware.long_tool_output:LongToolOutputMiddleware
    params:
      max_output_chars: 8000
      head_lines: 30
      tail_lines: 10
      head_chars: 4000
      tail_chars: 2000
```

参数解释：

| 参数 | 含义 | 我们的值 |
|---|---|---|
| `max_output_chars` | 工具返回总字符数低于这个值时**不做任何处理**直接放行 | `8000` |
| `head_lines` | 超过阈值后保留前 N 行 | `30` |
| `tail_lines` | 保留后 N 行 | `10` |
| `head_chars` | 头部最多保留 N 字符（防一行特别长的情况） | `4000` |
| `tail_chars` | 尾部最多保留 N 字符 | `2000` |

中间的部分被一行摘要替换，例如：

```
... [truncated 27 lines / 14_823 chars] ...
```

> **数字怎么定的**：8000 字符 ≈ 2 K tokens，对一个 NL2SQL 工具来说**足够看清楚一个完整结果**（30 行 ✕ 几列），但又不会让一次贪心 `SELECT *` 把 context 吃光。这是经验值，可以按你自己的模型 / 预算调。

---

## 跑那个贪心查询

```bash
dotenv run uv run nl2sql_agent/start.py "把 enterprise_basic 表所有字段全部列出来给我看看"
```

观察 trace(还是 stdout，跟第 4 章一样;CLI `./run-agent` 看更结构化的版本):模型还是会调 `execute_sql(sql="SELECT * FROM enterprise_basic LIMIT 50")`，工具实际**也跑出了**完整的 50 行——但是塞回 LLM 的那一份**已经被截过了**:

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

模型看到这一份足以告诉用户："这个表大概长这样，前几行是 X、Y、Z，一共 50 行"。**模型并不知道中间被截过**——它看到的就是工具返回。

**关键点**：截断只发生在 **进 message history 那一份** 上。`execute_sql` 自己拿到的、`bindings.py` 内部用的，都是完整结果。中间件只动 LLM 看到的那一份。

---

## 还有哪些中间件值得知道

`LongToolOutputMiddleware` 是最立竿见影的一个，但生产级 agent 通常会再叠几层：

### `ContextCompactionMiddleware` — 历史消息压缩

长对话跑久了，message history 会越积越大。这个中间件在接近 context 上限时**自动总结早期消息**，把"前 30 轮的工具调用 + 回复"压成一段几百字的摘要，再继续。

对 NL2SQL 不是必须，但如果用户开着同一个 session 问几十个问题，**没装这个就会撞 context 上限崩掉**。

```yaml
middlewares:
  - import: nexau.archs.main_sub.execution.middleware.long_tool_output:LongToolOutputMiddleware
    params:
      max_output_chars: 8000
      # ...
  - import: nexau.archs.main_sub.execution.middleware.context_compaction:ContextCompactionMiddleware
    params:
      trigger_ratio: 0.8        # 用到 80% context 时触发
      keep_recent_messages: 6   # 始终保留最近 6 条原文
```

### Tracing — Langfuse / OpenTelemetry

Tracing(链路追踪，把一次请求里发生的所有事件按时间顺序串起来，方便事后回放)。NexAU 支持把每一轮 LLM 调用 + 工具调用挂到 Langfuse(一个开源的 LLM 可观测平台，专门用来看智能体的 trace)。配置一般在 agent.yaml 同级的全局配置里，不严格属于 middleware 章节。**值得一提**:上线 NL2SQL 智能体的时候，Langfuse trace 是你**唯一**能搞清楚"为什么这个用户的查询答错了"的工具——它把每个 Skill 是否被读、每个 SQL 是怎么写出来的、每个工具返回是什么，全部串成一条可点击的时间线。

> 想接 Langfuse 的话，参考 NexAU 文档的 tracing 章节，本教程不展开。

### 你也可以写自己的 middleware

Middleware 就是一个 Python 类，实现 `before_tool_call` / `after_tool_call` 等钩子。比如你可以写一个 `RedactCreditCodeMiddleware`，在工具返回里自动把 `credit_code` 字段脱敏成 `***`。机制和写一个工具一样简单。本教程到此为止，留给你自己探索。

---

## 你刚才学到了什么

| 概念 | 你看到的 |
|---|---|
| **Middleware = 横切关注点** | 截断 / 压缩 / 日志 / tracing 都在这里 |
| **`import:` + `params:`** | YAML 里挂中间件的标准格式 |
| **`LongToolOutputMiddleware`** | NL2SQL 的标配，防 `SELECT *` 撑爆 context |
| **截断只动 LLM 看到的那一份** | 工具自己拿到的还是完整结果 |
| **数字要按你的模型/预算调** | 8000 chars / 30 head / 10 tail 是经验值 |

**渐进增强检查表**：

| | 第 4 章 | 第 5 章 |
|---|---|---|
| `agent.yaml` | tools + skills | **+ middlewares 7 行** |
| `bindings.py` | 100 行 | **未改动** |
| `tools/*.tool.yaml` | 2 个 | **未改动** |
| `skills/*/SKILL.md` | 7 个 | **未改动** |
| `system_prompt.md` | 7 步 | **未改动** |

第 5 章只多了 7 行 YAML。**没有任何代码改动**，但 agent 的"耐用度"上了一个台阶——它现在不会因为一次贪心查询就崩掉。

---

## 到这里 agent 已经是生产级了

回头看你已经写了什么：

```
nl2sql_agent/
├── agent.yaml             # ~50 行：llm/tools/skills/middlewares
├── system_prompt.md       # 7 步 workflow
├── bindings.py            # ~100 行：execute_sql + 安全护栏
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
├── start.py               # 一个简单的 CLI 入口
└── enterprise.sqlite
```

它有：

- **结构化、安全的工具**（第 2 章）
- **领域知识按需加载**（第 3 章）
- **多步任务规划**（第 4 章）
- **超长输出截断**（第 5 章）

剩下一件事：现在用的是 `openai_chat_completion` API。如果想换个 provider 跑（Anthropic / Gemini / OpenAI Responses API），要改什么？答：**两行 YAML**。

→ **第 6 章 · 跨 Provider 运行**
