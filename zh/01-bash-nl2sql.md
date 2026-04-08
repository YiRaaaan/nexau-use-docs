# 第 1 章 · 从做一个企业数据分析 Agent 开始

## 概述

NexAU 是一个**智能体脚手架**（agent harness）：核心循环与所有智能体框架相同，但工具系统、技能加载、上下文管理、跨 provider 适配这些"每个智能体都需要重复实现的部分"，NexAU 提供了一套开箱即用的实现。只需将配置与少量 Python 装配起来，无需从零实现一遍 LLM（Large Language Model，大语言模型）循环。

NexAU 适合以下场景：

- Agent 需要调用一组工具（查询数据库、读取文件、调用 API 等），并且希望工具的描述、参数、护栏与实现分离管理
- 希望 Agent 携带一批可按需加载的领域知识（每张表、每个业务域一份），而非全部塞进 system prompt
- 计划在不同 LLM 提供方（OpenAI、Anthropic、Gemini 等）之间切换而不重写代码

若只需让 LLM 执行单轮对话，直接使用 OpenAI 的 Python SDK 即可，无需引入框架。NexAU 所解决的是**多轮、有工具、有状态、需要持续演进**的场景。

## 本教程

本教程共 6 章，从最简形态的 SQL Agent 出发，逐章打磨至生产可用。每章仅在前一章代码基础上改动一两处，**每章结束时 Agent 均可完整运行**：

| 章 | 引入的能力 | Agent 的能力提升 |
|---|---|---|
| **1** | 复用内置 `run_shell_command` 工具 | 通过 `sqlite3` CLI 执行 SQL 查询 |
| 2 | 实现自定义工具 `execute_sql`，内置只读护栏 | 返回结构化结果，并拒绝任何写操作 |
| 3 | 引入 Skills 注入领域知识（每张表一份） | 掌握每张表的业务语义，减少列名猜测 |
| 4 | 接入 `write_todos` 规划工具 | 多表查询前自动制定执行计划 |
| 5 | 启用 `LongToolOutput` 中间件 | 自动截断超长结果，避免上下文溢出 |
| 6 | 切换 LLM Provider 协议 | 同一份 Agent 配置可运行于 OpenAI / Anthropic / Gemini |

---

## 示例场景

我们要构建一个企业数据分析 Agent——用户以自然语言提问，Agent 自行编写 SQL、查询数据库，再以自然语言返回结果。

数据库是 <a href="/enterprise.sqlite" download><code>enterprise.sqlite</code></a>，一个 SQLite 文件，只读，包含 7 张企业相关的表：

| 表名 | 描述 |
|---|---|
| `enterprise_basic` | 企业基本信息（注册地、规模、行业分类、专精特新等级……） |
| `enterprise_contact` | 企业联系方式（法人、电话、邮箱，均已脱敏） |
| `enterprise_financing` | 融资轮次与上市状态 |
| `enterprise_product` | 主营产品与知识产权 |
| `industry` | 行业链节点（树形结构，带 `chain_id` / `parent_id` / `chain_position`） |
| `industry_enterprise` | 企业 ↔ 行业链节点的多对多映射 |
| `users` | 平台用户账号（与企业表无关） |

7 张表通过 `credit_code`（统一社会信用代码）互相 join，每张表约 50 行。<a href="/enterprise.sqlite" download>点此下载</a>，后续所有章节均基于此数据库。

典型的提问：

> "海淀区有多少家小型企业?"
>
> "AI 产业链上游有哪些企业?"
>
> "找出注册资本最高的 5 家专精特新小巨人企业。"

## 环境准备

前置工作（安装 Python、`uv`、NexAU v0.4.1、`sqlite3`）已经在 [开始之前](./00-prerequisites.md) 做完。本章所有命令都在同一个 `nexau-tutorial/` 工作目录下执行：

```bash
cd nexau-tutorial
source .venv/bin/activate    # 如果你按 ch0 建了虚拟环境
```

Agent 背后由大模型负责思考、编写 SQL、生成回答。通过 `.env` 文件告诉 NexAU 调用哪个模型、API 入口以及所用密钥。在 `nexau-tutorial/` 下创建 `.env`：

```dotenv
LLM_MODEL=nex-agi/deepseek-v3.1-nex-1
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
```

将 `LLM_API_KEY` 替换为你自己的密钥。`LLM_BASE_URL` 是模型 API 入口，默认指向 OpenAI 协议端点——只要模型供应方兼容 OpenAI 协议，修改该行即可切换。

确认 `sqlite3` 命令行工具可用：

```bash
sqlite3 --version
```

若提示找不到命令，按系统环境安装：

- **macOS**：系统自带，一般无需安装。若使用 Homebrew 并希望使用新版本，`brew install sqlite`。
- **Linux**（Debian / Ubuntu）：`sudo apt-get install sqlite3`;CentOS / RHEL / Fedora：`sudo dnf install sqlite`。
- **Windows**：推荐 `winget install SQLite.SQLite`;或从 [sqlite.org/download.html](https://sqlite.org/download.html) 下载 `sqlite-tools-win-*.zip`，解压后将目录加入 `PATH`。亦可使用 `scoop install sqlite` / `choco install sqlite`。

安装完成后再次执行 `sqlite3 --version` 验证。

<a href="/enterprise.sqlite" download>下载 <code>enterprise.sqlite</code></a> 至 `nexau-tutorial/`，确认可以打开：

```bash
sqlite3 enterprise.sqlite ".tables"
# enterprise_basic       enterprise_product     industry_enterprise
# enterprise_contact     industry               users
# enterprise_financing
```

在 `nexau-tutorial/` 下新建项目目录：

```bash
mkdir enterprise_data_agent
```

> 本章后续命令均从 `nexau-tutorial/` 层执行。`enterprise_data_agent` 并非标准 Python 包（没有 `__init__.py`），但由于命令的当前目录正是其父目录，Python 会将当前目录加入 `sys.path`，`import enterprise_data_agent.bindings` 即可正常解析。若切换至其他目录执行命令，将出现 `ModuleNotFoundError: enterprise_data_agent`——属于预期行为，返回 `nexau-tutorial/` 后即可恢复。

---

## 系统提示

系统提示是 LLM 在每轮对话开始时都会读到的"使用说明"。它定义 Agent 的身份、能力与行为约束。LLM 此后的每个决定都会受这段文字影响，因此它必须写得明确——含糊的系统提示只会得到含糊的行为。

本教程中所有 system prompt 均采用英文撰写，原因是多数模型在英文 prompt 上的指令跟随更稳定;但**用户的提问与模型最终的回答都会自然落回中文**（因为下面这条 prompt 中写了 "Reply in the user's language"）。若测试后发现所用模型在中文 prompt 上同样稳定，直接替换为中文亦可。

创建 `enterprise_data_agent/system_prompt.md`：

```markdown
You are an enterprise data agent. The SQLite database `enterprise.sqlite` is in
the current working directory. It has 7 tables about Chinese enterprises;
tables that start with `enterprise_` join on `credit_code`.

Use `run_shell_command` to invoke `sqlite3`. Format:
`sqlite3 -header -column enterprise.sqlite "SELECT ... LIMIT 10;"`

## Workflow

1. **Discover schema if needed.** If you don't know a table's columns,
   run `.schema <table>` first.
2. **Write SELECT-only SQL.** SQLite syntax. Always include `LIMIT`.
3. **Execute via `run_shell_command`.** Read the formatted text output.
4. **Answer** in the user's language. End your message with the SQL you
   ran in a fenced block.

## Constraints

- SELECT only. No INSERT/UPDATE/DELETE/DROP, no destructive shell commands.
- Mock data: enterprise names look like `测试企业_N`. Don't pretend they are
  real companies.
```

三个值得注意的设计：

**唯一工具的明确声明。** 提示中直接告知 LLM 仅有 `run_shell_command` 一个工具。这避免它尝试调用不存在的工具，也避免它假设可以"直接执行 SQL"。

**示例精确的命令格式。** `sqlite3 -header -column enterprise.sqlite "..."` 这一行并非必需，但 LLM 倾向于"照例子操作"。给出具体格式，比抽象地要求"使用 sqlite3"可靠得多。

**只读约束写在提示里，不在代码里。** 这是第 1 章的关键弱点——所有安全保障都依赖 LLM 自觉遵守。一旦上下文被污染或被恶意输入诱导，这种约束即告失效。第 2 章将把约束下沉到工具实现中，把它从"软约束"升级为"硬约束"。

---

## agent.yaml

`agent.yaml` 是整个 Agent 的清单。它告诉 NexAU 使用哪个模型、读取哪份提示、挂载哪些工具。创建 `enterprise_data_agent/agent.yaml`：

```yaml
type: agent
name: enterprise_data_agent
description: Bash-only enterprise data agent (Chapter 1).
max_iterations: 20

system_prompt: ./system_prompt.md
tool_call_mode: structured

llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: openai_chat_completion
  temperature: 0.2
  stream: true

tools:
  - name: run_shell_command
    binding: nexau.archs.tool.builtin.shell_tools:run_shell_command
```

不到 20 行。几个值得注意的字段：

**`max_iterations: 20`** —— Agent 内部"思考 → 调用工具 → 获取结果 → 继续思考"的循环最多执行 20 轮，用于防止死循环。

**`${env.*}`** —— NexAU 在加载 YAML 时会解析这种占位符，从环境变量（或 `.env` 文件）读取值，从而避免 API key 直接出现在配置文件中。

**`temperature: 0.2`** —— 温度控制模型回答的随机性，取值范围通常为 0 到 2。值越高，模型越倾向于尝试不常见的词，适合写诗、命名这类需要创造性的场景;值越低，模型越倾向于选择概率最高的词，输出更稳定、更可复现。数据分析场景要求同一个问题每次都生成同一条 SQL，故将其压至 0.2。（注：推理模型 o1 / o3 / gpt-5 等不接受 temperature 参数，第 6 章会删除该字段。）

**`stream: true`** —— 流式输出。模型边生成边返回 token，而非等整段答案完成后一次性输出。开启后运行时可看到文字逐字出现，体验更接近 ChatGPT。

**`tool_call_mode: structured`** —— 控制 Agent 如何把"我要调用工具"这件事告诉 LLM。`structured` 使用 LLM 提供方原生的 function calling 接口——function calling 指 OpenAI / Anthropic / Gemini 在 API 层面为"模型决定调用某个函数并填入参数"这件事专门开放的接口，模型会返回结构化的 JSON，而不是混在普通文字中让调用方自行解析。另一种模式是通过提示词要求模型"欲调用工具时按某种格式输出"，再用正则匹配——可以运行但不够稳定。后续所有章节均使用 `structured`。

最关键的是 `tools` 块。它只挂载了一个工具——`run_shell_command`，并且没有为其配置 schema 文件（schema 即工具的"说明书"：告诉 LLM 工具名称、参数列表及参数类型，LLM 依据 schema 才知道如何调用）。整段 `tools` 配置仅两行：

```yaml
tools:
  - name: run_shell_command
    binding: nexau.archs.tool.builtin.shell_tools:run_shell_command
```

`binding` 的格式是 `Python 模块路径:函数名`。NexAU 启动时会 import 该函数，然后根据函数签名与 docstring 自动派生工具的参数 schema。换言之，**对于 NexAU 自带的内置工具，只需指定 binding 即可使用，无需编写代码与 schema 文件**。这是复用内置工具最短的路径。

> NexAU 的内置工具不止 shell 一个。`nexau.archs.tool.builtin` 下还提供读文件、写文件、搜索文件、维护任务清单等工具，后续章节将陆续使用。新建 Agent 前先浏览该目录，通常能节省可观的代码量。

---

## 入口

最后是启动 Agent 的 Python 入口。创建 `enterprise_data_agent/start.py`：

```python
"""Chapter 1 entry point — bash-only enterprise data agent."""

import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent

# 先将上一级目录的 .env 加载进环境变量，`LLM_API_KEY` 等会在 agent 启动前就绪
load_dotenv(HERE.parent / ".env")

from nexau import Agent, AgentConfig  # noqa: E402

config = AgentConfig.from_yaml(HERE / "agent.yaml")
agent = Agent(config=config)

question = " ".join(sys.argv[1:]) or "数据库里有哪些表？"
print(agent.run(question))
```

四件事：加载 `.env`、从 YAML 加载配置、构造 Agent、执行一次。`load_dotenv()` 必须在 `from nexau import ...` 之前调用，否则 NexAU 读取配置时环境变量仍为空。`agent.run(question)` 内部即"LLM 思考 → 工具调用 → 结果回灌 → LLM 继续思考"的循环——何时结束由 LLM 自主决定（认为问题已答完，或达到 `max_iterations` 上限）。

---

## 运行

确认当前仍在 `nexau-tutorial/` 目录下，执行：

```bash
uv run enterprise_data_agent/start.py "数据库里有哪些表？"
```

`uv run` 让命令在 NexAU 所在的 Python 环境中执行;`.env` 由 `start.py` 中的 `load_dotenv()` 自动加载，`LLM_API_KEY` 等环境变量会在 agent 启动前准备就绪。

应看到类似如下的输出：

```
我用 sqlite3 看一下数据库的表。

库里有 7 张表:enterprise_basic、enterprise_contact、enterprise_financing、
enterprise_product、industry、industry_enterprise、users。

​```sql
sqlite3 -header -column enterprise.sqlite ".tables"
​```
```

再尝试几个问题：

```bash
uv run enterprise_data_agent/start.py "海淀区有多少家小型企业？"
uv run enterprise_data_agent/start.py "enterprise_basic 表前 3 行长什么样？"
uv run enterprise_data_agent/start.py "users 表有几个 admin？"
```

每次回车后，后台的事件序列为：

1. NexAU 把系统提示、用户问题与 `run_shell_command` 工具的 schema 一起发送给 LLM
2. LLM 决定需要调用一次工具，返回一个工具调用，内容为 `sqlite3 ... "SELECT ..."`
3. NexAU 在本机执行这条命令，捕获 stdout / stderr / 退出码
4. 将命令输出作为工具结果回传给 LLM
5. LLM 根据结果判断问题已可回答，生成最终回复

这五步对使用者完全隐藏，你看到的只有一次 `agent.run()` 调用及其最终输出。

---

## 这一版提供了什么

不到 50 行 YAML + Python，已经涵盖了 NexAU 的几个核心特性：

| 特性 | 在本章的体现 |
|---|---|
| 声明式配置 | 整个 Agent 写在一份 YAML 中，Python 入口只负责装载与运行 |
| 零代码工具复用 | 一行 `binding` 即接入一个内置工具 |
| 环境变量插值 | `${env.LLM_MODEL}` 将敏感信息隔离在配置之外 |
| 跨 Provider 兼容 | 修改 `api_type` 即可切换到 Claude / Gemini |
| 自动的工具调用循环 | LLM ↔ 工具的多轮交互由框架管理 |

后续 5 章都在这个骨架之上增量扩展——更可靠的工具、更结构化的领域知识、规划能力、上下文护栏、provider 切换。骨架本身不会重写。

---

## 局限

第 1 版可以运行，但面对稍复杂的问题就会暴露出以下问题：

**字符串输入，而非结构化数据。** `sqlite3 -header -column` 输出的是格式化后的文本表格——LLM 必须自行数空格、对齐列名、将每行还原为字段。多数时候能做对，但不稳定。一个返回 `{"columns": [...], "rows": [...]}` 的工具会大幅减轻 LLM 的解析负担，也更可靠。

**安全依赖提示词，而非代码。** 系统提示写了 READ-ONLY，但 LLM 完全可能生成 `DELETE FROM enterprise_basic` 并交由 `run_shell_command` 实际执行。这种"软约束"在演示场景尚可，但任何接触真实用户输入的系统都不应依赖它。

**进程开销。** 每次工具调用都会启动一个 `sqlite3` 进程并在完成后退出。若在 Python 中直接通过 sqlite3 库连接数据库，可以保持长连接，延迟显著降低。

**LLM 不知道列名。** 模型对表结构没有任何先验知识，因此常需先执行一次 `.schema` 探查，再编写真正的查询——多耗一轮对话。7 张表、每张表十几列，每个新问题都要重新探查一次，浪费巨大。

后续章节将逐一解决这些问题。
