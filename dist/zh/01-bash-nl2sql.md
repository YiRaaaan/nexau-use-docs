# 第 1 章 · 从做一个 SQL 智能体开始

## 概述

NexAU 是一个**智能体脚手架**(agent harness):核心循环跟所有智能体框架一样，但工具系统、技能加载、上下文管理、跨 provider 适配这些"每个智能体都要做一遍的事",NexAU 提供了一套开箱即用的实现。你只需要把配置和少量 Python 装配起来，不用从头实现一遍 LLM(Large Language Model，大语言模型)循环。

NexAU 适合这种场景:

- 你的智能体需要调用一组工具(查数据库、读文件、调 API 等)，并且你希望工具的描述、参数、护栏跟实现分开管理
- 你想让智能体携带一批可按需加载的领域知识(每张表、每个业务域一份)，而不是把它们全塞进 system prompt
- 你打算在不同 LLM 提供方(OpenAI、Anthropic、Gemini 等)之间切换，而不重写代码

如果你只需要让 LLM 跑一次单轮对话，用 OpenAI 的 Python SDK 直接调就行，不需要框架。NexAU 解决的是**多轮、有工具、有状态、需要演化**的场景。

## 本教程

本教程分 6 章，从一个最简形态的 SQL 智能体出发，逐章把它打磨到生产可用。每一章只在前一章的代码基础上动一两个地方，**每一章结束时智能体都能完整跑起来**:

| 章 | 引入的能力 | 智能体的能力提升 |
|---|---|---|
| **1** | 复用内置 `run_shell_command` 工具 | 通过 `sqlite3` CLI 执行 SQL 查询 |
| 2 | 实现自定义工具 `execute_sql`，内置只读护栏 | 返回结构化结果，并拒绝任何写操作 |
| 3 | 引入 Skills 注入领域知识(每张表一份) | 掌握每张表的业务语义，减少列名猜测 |
| 4 | 接入 `todo_write` 规划工具 | 多表查询前自动制定执行计划 |
| 5 | 启用 `LongToolOutput` 中间件 | 自动截断超长结果，避免上下文溢出 |
| 6 | 切换 LLM Provider 协议 | 同一份智能体配置可运行于 OpenAI / Anthropic / Gemini |

---

## 示例场景

我们要构建一个 NL2SQL(Natural Language to SQL，自然语言转 SQL)智能体——用户用自然语言提问，智能体自己写 SQL、查数据库，再用自然语言把结果说出来。

数据库是 <a href="/enterprise.sqlite" download><code>enterprise.sqlite</code></a>，一个 SQLite 文件，只读，包含 7 张企业相关的表:

| 表名 | 描述 |
|---|---|
| `enterprise_basic` | 企业基本信息(注册地、规模、行业分类、专精特新等级……) |
| `enterprise_contact` | 企业联系方式(法人、电话、邮箱，均已脱敏) |
| `enterprise_financing` | 融资轮次与上市状态 |
| `enterprise_product` | 主营产品与知识产权 |
| `industry` | 行业链节点(树形结构，带 `chain_id` / `parent_id` / `chain_position`) |
| `industry_enterprise` | 企业 ↔ 行业链节点的多对多映射 |
| `users` | 平台用户账号(与企业表无关) |

7 张表通过 `credit_code`(统一社会信用代码)互相 join，每张表 50 行左右。<a href="/enterprise.sqlite" download>点这里下载</a>，后面所有章节都基于它。

典型的提问:

> "海淀区有多少家小型企业?"
>
> "AI 产业链上游有哪些企业?"
>
> "找出注册资本最高的 5 家专精特新小巨人企业。"

## 环境准备

clone 框架源码、cd 进去、装成可编辑包，后面整章都待在这个目录里:

```bash
git clone https://github.com/nex-agi/NexAU.git
cd NexAU
uv pip install -e .   # 或 pip install -e .
```

`uv` 是新一代的 Python 包管理工具，跑得比 `pip` 快很多;装不上的话直接用 `pip install -e .` 也可以。`-e .` 的意思是"以可编辑模式安装当前目录的包"——你改 NexAU 源码，改动立刻生效，不用重装。

智能体背后是一个大模型在思考、写 SQL、回答你的问题。我们用一个 `.env` 文件告诉 NexAU 调哪个模型、API 在哪、用什么 key。在 `NexAU/` 下创建 `.env`:

```dotenv
LLM_MODEL=nex-agi/deepseek-v3.1-nex-1
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
```

把 `LLM_API_KEY` 换成你自己的 key。`LLM_BASE_URL` 是模型 API 的入口，默认指向 OpenAI 协议的端点——只要你的模型供应方兼容 OpenAI 协议，改这一行就能切。

确认 `sqlite3` 命令行工具可用:

```bash
sqlite3 --version
```

如果提示找不到命令，按你的系统装一下:

- **macOS**:系统自带，通常不用装。如果用了 Homebrew 想要新版本，`brew install sqlite`。
- **Linux**(Debian / Ubuntu):`sudo apt-get install sqlite3`;CentOS / RHEL / Fedora:`sudo dnf install sqlite`。
- **Windows**:推荐 `winget install SQLite.SQLite`，或者去 [sqlite.org/download.html](https://sqlite.org/download.html) 下 `sqlite-tools-win-*.zip`，解压后把目录加到 `PATH`。也可以直接 `scoop install sqlite` / `choco install sqlite`。

装完再跑一次 `sqlite3 --version` 验证。

<a href="/enterprise.sqlite" download>下载 <code>enterprise.sqlite</code></a> 到 `NexAU/`，确认能打开:

```bash
sqlite3 enterprise.sqlite ".tables"
# enterprise_basic       enterprise_product     industry_enterprise
# enterprise_contact     industry               users
# enterprise_financing
```

在 `NexAU/` 下新建项目目录:

```bash
mkdir nl2sql_agent
```

> 整章后面所有命令都从 `NexAU/` 这一层发出。`nl2sql_agent` 不是一个正经 Python 包(我们不会写 `__init__.py`)，但因为命令的当前目录就是它的父目录，Python 会把当前目录加进 `sys.path`,`import nl2sql_agent.bindings` 自然就能找到。如果你换到别的目录跑命令，会看到 `ModuleNotFoundError: nl2sql_agent`——这是预期行为，回到 `NexAU/` 再跑就好。

> 想直接看成品而不是一行行敲?nexau-use-docs 文档仓库根目录下就有一份完整的 `nl2sql_agent/`，把它整个复制到 `NexAU/` 下也能跑——文件结构跟下面教程里手写的完全一致。

---

## 系统提示

系统提示是 LLM 在每一轮对话开始时都会读到的"使用说明"。它定义了智能体的身份、能力、行为约束。LLM 之后的每一个决定都会受这段话影响，所以它需要写得明确——含糊的系统提示会得到含糊的行为。

本教程里所有 system prompt 都用英文写，原因是大多数模型在英文 prompt 上的指令跟随更稳;但**用户的提问和模型最终的回答都会自然落回中文**(因为下面这条 prompt 里写了 "Reply in the user's language")。如果你测试一遍发现自家模型在中文 prompt 上同样稳，直接换成中文也行。

创建 `nl2sql_agent/system_prompt.md`:

```markdown
You are an NL2SQL agent. The SQLite database `enterprise.sqlite` is in
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

三个值得注意的设计:

**唯一工具的明确声明。** 提示里直接告诉 LLM 它只有一个工具叫 `run_shell_command`。这避免它去尝试调用不存在的工具，也避免它假设可以"直接执行 SQL"。

**示例精确的命令格式。** `sqlite3 -header -column enterprise.sqlite "..."` 这一行不是必须的，但 LLM 倾向于"照着例子来"。给出一行具体格式，比抽象地说"使用 sqlite3"要可靠得多。

**只读约束写在提示里，不在代码里。** 这是第 1 章的关键弱点——所有安全保障都依赖 LLM 自己"听话"。当上下文被污染、或被恶意输入诱导时，这种约束会失效。第 2 章会把约束移到工具实现里，让它从"软约束"变成"硬约束"。

---

## agent.yaml

`agent.yaml` 是整个智能体的清单。它告诉 NexAU 用哪个模型、读哪份提示、有哪些工具。创建 `nl2sql_agent/agent.yaml`:

```yaml
type: agent
name: nl2sql_agent
description: Bash-only NL2SQL agent (Chapter 1).
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
    binding: nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command
```

不到 20 行。几个不那么显然的字段:

**`max_iterations: 20`** —— 智能体内部"思考 → 调工具 → 拿结果 → 接着思考"的循环最多跑 20 轮。这是死循环的安全阀。

**`${env.*}`** —— NexAU 在加载 YAML 时会解析这种占位符，从环境变量(或 `.env` 文件)取值。这样 API key 永远不会出现在配置文件里。

**`temperature: 0.2`** —— 温度控制模型回答的随机性，范围一般是 0 到 2。值越高，模型越倾向于尝试不那么常见的词，适合写诗、起名这种要创造性的场景;值越低，模型越倾向于挑概率最高的那个词，输出更稳定、更可复现。NL2SQL 我们要的是同一个问题每次都生成同一句 SQL，所以压到 0.2。(注:推理模型 o1 / o3 / gpt-5 那一类不接受 temperature 参数，第 6 章会把这个字段去掉。)

**`stream: true`** —— 流式输出。模型一边生成一边把 token 返回，而不是等整段答案写完再一次性吐出来。打开它运行时能看到字逐个蹦出来，体验更接近 ChatGPT。

**`tool_call_mode: structured`** —— 控制智能体怎么把"我要调工具"这件事告诉 LLM。`structured` 用的是 LLM 提供方原生的 function calling 接口——所谓 function calling，就是 OpenAI / Anthropic / Gemini 在 API 层面专门为"模型决定调用某个函数，并填好参数"这件事开的一个口子，模型会返回一个结构化的 JSON，而不是混在普通文字里让你自己 parse。相对的另一种模式是用提示词指示模型"想调工具就按这种格式输出"，再用正则去抠——能跑但不稳定。后面所有章节都用 `structured`。

最关键的是 `tools` 块。它只挂了一个工具——`run_shell_command`，而且没有给它配套的工具 schema 文件(schema 就是工具的"说明书":告诉 LLM 这个工具叫什么、有哪些参数、参数是什么类型，LLM 看了 schema 才知道怎么调用)。整段 `tools` 配置只有两行:

```yaml
tools:
  - name: run_shell_command
    binding: nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command
```

`binding` 的格式是 `Python 模块路径:函数名`。NexAU 启动时会去 import 这个函数，然后从函数签名和 docstring 自动派生工具的参数 schema。换句话说，**对于 NexAU 自带的内置工具，你只要指一下 binding 就能用，不用写一行代码、也不用写 schema 文件**。这是复用内置工具的最短路径。

> NexAU 的内置工具不止 shell 一个。`nexau.archs.tool.builtin` 下还有读文件、写文件、搜索文件、维护任务清单等工具。后面几章会陆续用到。新建智能体之前先翻一眼这个目录通常能省不少代码。

---

## 入口

最后是把智能体跑起来的 Python 入口。创建 `nl2sql_agent/start.py`:

```python
"""Chapter 1 entry point — bash-only NL2SQL agent."""

import sys
from pathlib import Path

from nexau import Agent, AgentConfig

HERE = Path(__file__).resolve().parent

config = AgentConfig.from_yaml(HERE / "agent.yaml")
agent = Agent(config=config)

question = " ".join(sys.argv[1:]) or "数据库里有哪些表？"
print(agent.run(question))
```

三件事:从 YAML 加载配置、构造智能体、跑一次。`agent.run(question)` 内部就是那个"LLM 思考 → 工具调用 → 结果回灌 → LLM 接着思考"的循环——什么时候结束由 LLM 自己决定(它觉得问题答完了，或者达到 `max_iterations` 上限)。

---

## 运行

确保你还在 `NexAU/` 目录，然后:

```bash
dotenv run uv run nl2sql_agent/start.py "数据库里有哪些表？"
```

`dotenv run` 会先把 `.env` 里的变量加载到环境变量里，再跑后面的命令;`uv run` 让命令在 NexAU 装好的那套 Python 环境里执行。两个加在一起，等价于"先 source `.env`，再用项目环境的 python 跑 `nl2sql_agent/start.py`"。

应该看到类似的输出:

```
我用 sqlite3 看一下数据库的表。

库里有 7 张表:enterprise_basic、enterprise_contact、enterprise_financing、
enterprise_product、industry、industry_enterprise、users。

​```sql
sqlite3 -header -column enterprise.sqlite ".tables"
​```
```

再换几个问题:

```bash
dotenv run uv run nl2sql_agent/start.py "海淀区有多少家小型企业？"
dotenv run uv run nl2sql_agent/start.py "enterprise_basic 表前 3 行长什么样？"
dotenv run uv run nl2sql_agent/start.py "users 表有几个 admin？"
```

每一次回车，后台的事件序列是:

1. NexAU 把系统提示、用户问题、和 `run_shell_command` 工具的 schema 一起发给 LLM
2. LLM 决定它需要调一次工具，返回一个工具调用，内容是 `sqlite3 ... "SELECT ..."`
3. NexAU 在你机器上执行这条命令，捕获 stdout / stderr / 退出码
4. 把命令输出作为工具结果回传给 LLM
5. LLM 看到结果，决定问题已经能答了，生成最终回复

这五步对你完全隐藏，你看到的只有一次 `agent.run()` 调用和它的最终输出。

---

## 这一版给了你什么

不到 50 行 YAML + Python，你已经看到了 NexAU 的几个核心特性:

| 特性 | 在这一章里的体现 |
|---|---|
| 声明式配置 | 整个智能体写在一份 YAML 里，Python 入口只负责"装载并运行" |
| 零代码工具复用 | 一行 `binding` 就接入了一个内置工具 |
| 环境变量插值 | `${env.LLM_MODEL}` 把敏感信息隔离在配置之外 |
| 跨 Provider 兼容 | 改 `api_type` 就能切换到 Claude / Gemini |
| 自动的工具调用循环 | LLM ↔ 工具的多轮来回由框架管理 |

后面 5 章都是在这个骨架上加东西——更靠谱的工具、更结构化的领域知识、规划能力、上下文护栏、provider 切换。骨架不会重写。

---

## 局限

第 1 版能跑,但跑几个稍复杂的问题就会发现下面这些问题:

**字符串输入，而不是结构化数据。** `sqlite3 -header -column` 输出的是格式化后的文本表格——LLM 必须自己数空格、对齐列名、把每一行切回字段。它大部分时候做得对，但不稳定。一个返回 `{"columns": [...], "rows": [...]}` 的工具会让 LLM 的工作轻松得多，也更可靠。

**安全靠提示词，不靠代码。** 系统提示里写了 READ-ONLY，但实际上 LLM 完全可以生成 `DELETE FROM enterprise_basic` 然后让 `run_shell_command` 真的执行它。这种"软约束"在演示场景能用，但任何接触真实用户输入的系统都不能这么做。

**进程开销。** 每一次工具调用都启动一个 `sqlite3` 进程，执行完退出。如果在 Python 里直接用 sqlite3 库连数据库，可以保持长连接，延迟会显著降低。

**LLM 不知道列名。** 模型没有任何关于表结构的先验知识，所以经常要先跑一次 `.schema` 探一下，再写真正的查询——多花一轮对话。一个数据库 7 张表、每张表十几列，每个新问题都要重新探一遍是巨大的浪费。

这些问题会在后面的章节被逐一解决。
