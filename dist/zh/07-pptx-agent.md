# 第 7 章 · 加一个做 PPT 的技能

**TL;DR**：给企业数据分析 Agent 挂上 Anthropic 官方的 `pptx` Skill 和三个内置工具，它就能根据查询结果自动写 `pptxgenjs` 脚本、跑 `node`、生成一份配色不糟、数据真实、SQL 可追溯的 `.pptx`。`agent.yaml` 多 4 行，`system_prompt.md` 多一段，`bindings.py` 一行不动。

> **本章假设你**已经跟着第 1–6 章把企业数据分析 Agent 跑起来过。如果还没，先回到[第 1 章](./01-bash-nl2sql.md)。

## 你最后会拿到什么

跑完本章，你的智能体会有两种工作模式：

- **Mode A**（默认）：问"海淀区有多少家小型企业?"——返回一段自然语言 + SQL，跟第 5 章完全一样
- **Mode B**：问"给我做一份海淀区 TOP 10 注册资本企业的简报 PPT"——智能体自己读设计 Skill、查数据、写 JS、跑 `node`、最后告诉你 `output/haidian_top10.pptx` 已经生成

切换靠的是 prompt 里的几行话，不是新代码。

## 第 6 章卡在哪

到第 6 章为止，智能体的输出永远是**一段文字 + 一段 SQL**。但业务方要的不是这个，是**一份可以直接发出去的报告**：海淀区 TOP 10 简报、专精特新分布概览、季度融资榜的 PPT。

补这块能力，有两条路：

1. **手写一个 PPT 工具**：在 `bindings.py` 里维护模板和填槽逻辑——脆、难维护、每出一种新报告都要改代码
2. **教模型自己写 PPT 代码**：给它一个 Skill 讲怎么用 `pptxgenjs`、再给它几个能写文件和跑 shell 的内置工具

第二条路就是这一章。**整章核心代码变更只有 `agent.yaml` 多 4 行 + `system_prompt.md` 多一段。**

## 思路

NexAU 加新能力，看你想加的是什么：

- **加新工具**（第 2 章 ExecuteSQL、第 4 章 todo_write）→ 让框架知道怎么"做新事情"
- **加新 Skill**（第 3 章每张表一个 SKILL.md）→ 让模型知道怎么"用已有的工具"

这一章两样都要：

| 加的东西 | 类型 | 作用 |
|---|---|---|
| `pptx` Skill （Anthropic 出品） | Skill | 教模型怎么设计 PPT、怎么用 `pptxgenjs`、用什么色板和字体 |
| `write_file` | NexAU 内置工具 | 让模型把生成的 JS 脚本写到磁盘 |
| `run_shell_command`（第 1 章已经认识） | NexAU 内置工具 | 跑 `node generate.js` 执行脚本 |
| `read_file` | NexAU 内置工具 | 让模型在需要时回读 `pptxgenjs.md` 子文档 |

模型最终的工作流是：**查数据 → 设计 PPT → 写 JS → 跑 node → 报告文件路径**。

## 第 1 步：装 Node.js + pptxgenjs

`pptxgenjs` 是 Node.js 库。如果机器上还没有 Node：

- **macOS**:`brew install node`
- **Linux** （Debian / Ubuntu）：`sudo apt-get install nodejs npm`，或用 [nvm](https://github.com/nvm-sh/nvm) 装更新版
- **Windows**:`winget install OpenJS.NodeJS`

装好之后，在 `NexAU/` 下装 `pptxgenjs`：

```bash
cd NexAU
npm init -y > /dev/null
npm install pptxgenjs
```

这会创建一个 `node_modules/`。本章的智能体会从 `NexAU/` 跑 `node`，所以脚本能直接 `require("pptxgenjs")`。

验证：

```bash
node -e "console.log(require('pptxgenjs').version)"
# 3.12.0 或更新
```

## 第 2 步：装 pptx Skill

`pptx` 是 Anthropic 维护的官方 Skill，直接用 `npx skills` 装到全局：

```bash
npx skills add anthropics/skills@pptx -g -y
```

装完它会落到 `~/.agents/skills/pptx/`，长这样：

```
~/.agents/skills/pptx/
├── SKILL.md          # 入口:设计原则、色板、字体、QA workflow
├── pptxgenjs.md      # 完整的 pptxgenjs API 教程
├── editing.md        # 改已有 .pptx 的 workflow
└── scripts/          # 配套的 Python 脚本(本章不用)
```

把这个文件夹**软链**到智能体的 skills 目录（也可以复制，但软链更新方便）：

```bash
cd NexAU
ln -s ~/.agents/skills/pptx enterprise_data_agent/skills/pptx
```

验证：

```bash
ls -l enterprise_data_agent/skills/pptx
# 应该看到一个指向 ~/.agents/skills/pptx 的箭头
```

> **为什么 pptx Skill 这么大?** 第 3 章我们写的 Skill 每个只有几十行 schema + 几条 example——那是**领域知识 Skill**。pptx Skill 不一样，它是**领域工作流 Skill**：一整套"怎么从零设计一份不丑的 PPT"的方法论，包括 10 套预设色板、字体配对、布局类型、必须做的 QA 步骤。Claude Skills 格式同时支持这两种用法，NexAU 的 Skill 加载器对它们一视同仁。

## 第 3 步：改 `agent.yaml`

打开 `enterprise_data_agent/agent.yaml`，在 `tools:` 段加三个内置工具，在 `skills:` 段加 pptx：

```yaml
tools:
  - name: execute_sql
    yaml_path: ./tools/ExecuteSQL.tool.yaml
    binding: enterprise_data_agent.bindings:execute_sql

  - name: todo_write
    yaml_path: ./tools/TodoWrite.tool.yaml
    binding: nexau.archs.tool.builtin.todo_write:todo_write

  # 第 7 章新增:让智能体能把生成的 JS 脚本写到磁盘
  - name: write_file
    binding: nexau.archs.tool.builtin.file_tools:write_file

  # 第 7 章新增:跑 node generate.js
  - name: run_shell_command
    binding: nexau.archs.tool.builtin.shell_tools.run_shell_command:run_shell_command

  # 第 7 章新增:让模型在需要细节的时候回读 pptxgenjs.md
  - name: read_file
    binding: nexau.archs.tool.builtin.file_tools:read_file

skills:
  - ./skills/enterprise_basic
  - ./skills/enterprise_contact
  - ./skills/enterprise_financing
  - ./skills/enterprise_product
  - ./skills/industry
  - ./skills/industry_enterprise
  - ./skills/users

  # 第 7 章新增
  - ./skills/pptx
```

`write_file` 和 `read_file` 用的是第 4 章讲过的"只写 binding、不写 yaml_path"的快捷写法——框架从 Python 函数签名自动生成 schema。pptx Skill 给的是工作流知识不是数据库知识，但 NexAU 不在乎，挂到 `skills:` 就完事。

## 第 4 步：改 system prompt

模型现在多了一种"完成方式"：除了"回答问题"，还能"产出一份 PPT"。需要在 system prompt 里告诉它什么时候选哪种。打开 `enterprise_data_agent/system_prompt.md`，在 Workflow 段后面加一段 Output Modes：

```markdown
## Output Modes

You have two ways to deliver an answer. **Pick based on what the user asks for**, not on your own preference.

### Mode A — Plain answer (default)

When the user asks a question and just wants the answer, reply in chat:
- A short, natural-language answer grounded in the actual rows
- The SQL you ran in a fenced block

This is the default. Use it unless the user explicitly asks for a deck, slides, presentation, report file, or `.pptx`.

### Mode B — Generate a `.pptx`

When the user asks for a "PPT", "deck", "slides", "presentation", "汇报", "简报", or "报告文件":

1. **Read the `pptx` skill first.** Always. It contains design rules, color palettes, and the `pptxgenjs` API. Your first instinct on layout and color will be wrong — read it.
2. **Query the data** with `execute_sql`. Get *all* the rows you need before writing any JS.
3. **Plan slide-by-slide.** A good data analysis deck is 4–8 slides:
   - Title slide (topic + date)
   - 1–2 slides of headline numbers (large stat callouts)
   - 1–3 slides of breakdowns (top-N tables, comparisons)
   - Summary / takeaways slide
4. **Pick a color palette from the pptx skill** that matches the topic. Don't default to blue.
5. **Write a JS script** with `pptxgenjs` and save it via `write_file` to `output/<topic>.js`. The script should `require("pptxgenjs")`, build the slides, and call `pres.writeFile({ fileName: "output/<topic>.pptx" })`.
6. **Run it** with `run_shell_command`: `node output/<topic>.js`. The cwd is `NexAU/`, so `require("pptxgenjs")` resolves through the local `node_modules`.
7. **Reply** with the file path and a one-line summary of what's in the deck. End with the SQL you ran.

### Hard rules for PPT generation

- **Numbers come from `execute_sql` only.** Never make up data. If a query returns 0 rows, say so and stop — don't fill the slide with placeholders.
- **No charts in v1.** `pptxgenjs` supports charts but they're easy to get wrong. Use big stat callouts and tables.
- **Output goes under `output/`.** Create the folder if it doesn't exist (`mkdir -p output` via `run_shell_command`).
```

跟前面几章一样，整个 prompt 的其它段（Workflow、Constraints）不动，只多一个 Output Modes 段。

## 跑

先确认改 prompt 没把原来的功能弄坏：

```bash
uv run enterprise_data_agent/start.py "海淀区有多少家小型企业?"
```

应该跟第 5 章一样，纯文字回答，不会生成 PPT。这是 Mode A。

现在试 Mode B：

```bash
uv run enterprise_data_agent/start.py "给我做一份海淀区 TOP 10 注册资本企业的简报 PPT"
```

观察 trace，你会看到大致这样的事件序列：

1. `read_skill(name="pptx")` —— 读 pptx Skill 的 SKILL.md
2. `read_skill(name="enterprise_basic")` —— 读企业基本信息表的 Skill，看 `register_capital` 列的坑点
3. `execute_sql(sql="SELECT enterprise_name, CAST(register_capital AS REAL) AS cap FROM enterprise_basic WHERE register_district = '海淀区' ORDER BY cap DESC LIMIT 10")`
4. （可能）`read_file(path="enterprise_data_agent/skills/pptx/pptxgenjs.md")` —— 对某个 API 不确定时回头读子文档
5. `run_shell_command(command="mkdir -p output")`
6. `write_file(path="output/haidian_top10.js", content="const pptxgen = require('pptxgenjs'); ...")`
7. `run_shell_command(command="node output/haidian_top10.js")`
8. 最终回复："`output/haidian_top10.pptx` 已生成，共 5 页：封面、TOP 3 大数字、TOP 4–10 表格、行业分布、总结。"

打开 `NexAU/output/haidian_top10.pptx`（macOS 上 `open output/haidian_top10.pptx`、Linux 上 `xdg-open`、Windows 双击），应该能看到一份配色不糟、数据真实、SQL 可追溯的 PPT。

再试一个跨表的：

```bash
uv run enterprise_data_agent/start.py "给我做一份各专精特新等级企业数量 + 主营行业分布的简报"
```

这一次模型会：
- 读 `enterprise_basic` Skill（知道 `zhuanjingtexin_level` 列）
- 读 `industry` + `industry_enterprise` Skill（知道怎么 join 行业链）
- 调多次 `execute_sql` 拿不同维度的数据
- 用 `todo_write` 把"3 个查询 + 1 个 PPT 生成"拆成 4 步追踪
- 生成一份多页 PPT

**前 6 章建好的所有能力都派上了用场**——结构化工具、Skills、规划、长输出截断、跨 Provider——pptx 只是又一个 Skill，叠在已有的栈上。

## 这一版给了你什么

| 概念 | 在这一章里的体现 |
|---|---|
| Skill 不止能装领域知识 | pptx 装的是"领域工作流"——一整套设计 PPT 的方法论 |
| 第三方 Skill 能直接复用 | Anthropic 的 pptx Skill 一个 `ln -s` 就接到智能体上 |
| 内置工具的组合表达力 | `write_file` + `run_shell_command` 几乎能做任何"生成 + 执行"型任务 |
| 一个智能体可以有多种输出模式 | 同一个 `agent.yaml` 既能回答问题也能生成文件，靠 prompt 里的 Output Modes 路由 |

**渐进检查表**：

| | 第 5 章 | 第 7 章 |
|---|---|---|
| `agent.yaml` `tools:` | 2 个 | **+3 个内置工具（read_file / write_file / run_shell_command）** |
| `agent.yaml` `skills:` | 7 个 | **+1 个 pptx** |
| `bindings.py` | 100 行 | **未改动** |
| `tools/*.tool.yaml` | 2 个 | **未改动** |
| `system_prompt.md` | 7 步 Workflow | **+1 段 Output Modes** |
| 新增依赖 | —— | Node.js + `pptxgenjs` |

智能体的全部 PPT 生成能力都来自模型自己读 pptx Skill 后写出来的 JS 代码——你不用维护任何 PPT 模板。

## 局限与权衡

跑几次之后，几个真实的痛点会冒出来。这里把它们说清楚，而不是假装本章交付了一个完美方案。

**没有图表。** 我们在 Hard rules 里禁用了 `pptxgenjs` 的 chart API。第一次实验时打开它，模型大概率会把数据维度搞错——比如把日期排成 Y 轴、把企业名排成图例。要让图表稳定，通常的做法是：让 Python（matplotlib / plotly）在 `execute_sql` 之外另起一个工具生成 PNG，再让 JS 用 `slide.addImage()` 嵌进去。这条路本章没走，留作扩展。

**设计同质化。** pptx Skill 给了 10 套色板，但模型在没有具体引导时倾向于挑前几套。如果你要给客户做严肃汇报，在 prompt 里指定"用 Midnight Executive 色板"或者"用公司主色 #xxxxxx"会更稳。

**视觉 QA 没有自动化。** pptx Skill 的 SKILL.md 末尾有一整套"渲染成图 → 用子智能体看图找 bug"的 QA workflow。本章没装那条管道（需要 LibreOffice + Poppler + 子智能体调度）。如果要把这个智能体放到生产环境给真用户用，把 QA loop 接上是必须的——这刚好是 NexAU 子智能体的典型用例。

**单文件输出，不支持模板。** 我们走的是 pptx Skill 的"从零创建"路径（`pptxgenjs`）。如果你已经有公司模板 `.pptx` 文件，想往里塞数据，要走的是另一条路径——`editing.md` 里讲的 `python-pptx` + 模板 unpack/pack。同一个 pptx Skill 已经覆盖了这条路径，只是本章没用。

## 完整的 0 → 1 教程到这儿就结束了

你已经从一个"能跑一次 SQL 的 shell 智能体"一路加到了"能基于 7 张表的真实数据自动生成简报 PPT 的多模态智能体"。回头看你写过的代码：

```
enterprise_data_agent/
├── agent.yaml             # ~60 行: llm + tools + skills + middlewares
├── system_prompt.md       # 7 步 Workflow + Output Modes
├── bindings.py            # ~100 行: execute_sql + 安全护栏
├── tools/
│   ├── ExecuteSQL.tool.yaml
│   └── TodoWrite.tool.yaml
└── skills/
    ├── enterprise_*/
    ├── industry*/
    ├── users/
    └── pptx -> ~/.agents/skills/pptx
```

不到 200 行代码，7 章下来：

- **结构化、安全的工具**（第 2 章）
- **领域知识按需加载**（第 3 章）
- **多步任务规划**（第 4 章）
- **超长输出截断**（第 5 章）
- **跨四种 LLM 协议**（第 6 章）
- **多输出模式 + 第三方 Skill 复用**（第 7 章）

剩下的工作不再是"框架问题"，是**产品问题**——迭代你的 Skill、给特定客户调色板、接上 tracing、把这个智能体放到一个真正的 UI 后面。框架的活儿干完了。

## 延伸阅读

- [Anthropic Skills 仓库](https://github.com/anthropics/skills) —— pptx 之外还有 docx、xlsx、pdf 等官方 Skill，接入方式跟本章一样
- [pptxgenjs 官方文档](https://gitbrent.github.io/PptxGenJS/) —— 想打开 chart API 的话从这里查
- [第 3 章 · 写自己的 Skill](./03-skills.md) —— 想为自己的业务领域写一个工作流 Skill 的话，从这一章的格式起步
