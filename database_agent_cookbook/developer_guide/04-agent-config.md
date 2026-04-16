# 第 4 章 · Agent 配置参考

> **目标**：理解 `agent.yaml` 和 `nexau.json` 的每个字段，能够根据需求自行调整配置。

---

## agent.yaml

以下是书店 Agent 的完整配置示例：

```yaml
type: agent
name: bookstore_agent
description: 回答关于书店数据库的自然语言问题。

system_prompt: ./system_prompt.md
system_prompt_type: file
max_iterations: 50
tool_call_mode: structured

llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: openai_chat_completion
  temperature: 0.2
  stream: true

skills:
  - ./skills/customers
  - ./skills/books
  - ./skills/orders
```

### 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `type` | 是 | 固定为 `agent` |
| `name` | 是 | Agent 名称，用于标识和日志 |
| `description` | 否 | Agent 的一句话描述 |
| `system_prompt` | 是 | System Prompt 文件路径或内联文本 |
| `system_prompt_type` | 是 | `file`（从文件读取）或 `inline`（直接写在 yaml 中） |
| `max_iterations` | 否 | 最大迭代次数，默认 20。挂载 Skills 后建议调至 30-50，因为模型需要额外的轮次读取 Skill |
| `tool_call_mode` | 否 | `structured`（推荐）= 结构化工具调用 |

### llm_config

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | 模型名称 |
| `base_url` | 是 | API 地址 |
| `api_key` | 是 | API 密钥 |
| `api_type` | 否 | `openai_chat_completion`（默认） |
| `temperature` | 否 | 温度。数据库查询建议 0.1-0.3（需要精确性），创意任务可调高 |
| `stream` | 否 | 是否流式输出，默认 `true` |

**环境变量语法**：`${env.VAR_NAME}` 会在 Agent 启动时替换为环境变量 `VAR_NAME` 的值。敏感信息（API Key）务必使用环境变量，不要硬编码在 yaml 中。

### skills

```yaml
skills:
  - ./skills/customers
  - ./skills/books
  - ./skills/orders
```

每一项是**指向 Skill 文件夹的相对路径**（不是 `SKILL.md` 文件本身）。框架启动时会扫描各文件夹下的 `SKILL.md`，将 frontmatter 中的 `name`/`description` 注册为可用 Skill。

**背后的机制**：
- 所有 Skill 的 `description` 在 Agent 启动时拼入 system prompt，告知模型"你有这些 Skill 可用"
- 正文不会进入 context——仅当模型决定读取某个 Skill 时，正文才被注入
- `read_skill` 工具由框架自动注入，无需在 `tools:` 中声明

### tools（可选）

本指南中 SQL 查询由平台内置工具提供，因此不需要 `tools:` 段。如果你需要额外的自定义工具，格式如下：

```yaml
tools:
  - name: my_tool
    yaml_path: ./tools/MyTool.tool.yaml
    binding: tools.my_tool:my_tool_func
```

---

## nexau.json

项目根目录下的 `nexau.json` 是 NexAU 的项目清单文件：

```json
{
  "agents": {
    "bookstore_agent": "agent.yaml"
  },
  "excluded": [
    ".nexau/",
    ".env",
    "__pycache__/"
  ]
}
```

| 字段 | 说明 |
|---|---|
| `agents` | Agent 名称 → 配置文件路径的映射 |
| `excluded` | 部署时排除的文件/目录 |

**多 Agent 场景**：一个项目可以包含多个 Agent：

```json
{
  "agents": {
    "bookstore_agent": "agents/bookstore/agent.yaml",
    "inventory_agent": "agents/inventory/agent.yaml"
  }
}
```

---

## 环境变量配置

创建 `.env` 文件（已在 `nexau.json` 的 `excluded` 中，不会被部署）：

```bash
LLM_MODEL=your-model-name
LLM_BASE_URL=https://your-llm-api.com/v1
LLM_API_KEY=sk-xxx
```

---

## 完整示例

`examples/bookstore_agent/` 目录下包含一个可直接使用的完整示例：

```
examples/bookstore_agent/
├── nexau.json
├── agent.yaml
├── system_prompt.md
└── skills/
    ├── customers/SKILL.md
    ├── books/SKILL.md
    └── orders/SKILL.md
```

可直接复制该目录作为你自己 Agent 的起点：

```bash
cp -r examples/bookstore_agent/ my_agent/
```

然后修改 Skills 和 System Prompt 以适配你的数据库。

---

## 小结

| 要点 | 说明 |
|---|---|
| `agent.yaml` 是唯一的配置文件 | 定义 LLM、Skills、工具 |
| SQL 工具由平台内置 | 无需在 `tools:` 中声明 |
| `${env.VAR}` 用于敏感信息 | API Key 不要硬编码 |
| `nexau.json` 是项目清单 | 声明有哪些 Agent |
| `max_iterations` 注意调高 | 挂载 Skills 后建议 30-50 |
