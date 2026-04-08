# 第 6 章 · 跨 Provider 运行

前面 5 章已将企业数据分析 Agent 完整构建——但仅运行在 OpenAI Chat Completions 协议上。第 6 章不引入新功能，只回答一个问题：**同一份 `agent.yaml`（相同的工具、相同的 Skill、相同的系统提示），如何切换到 Anthropic Claude / Google Gemini / OpenAI Responses 上运行？**

答案：**只修改 `llm_config` 这一块**，其余完全不动。

## 为什么可以这样做

NexAU 的核心职责之一是协议翻译。第 2 章编写的 `ExecuteSQL.tool.yaml`，运行时 NexAU 会根据 `api_type` 将其中的 JSON Schema 自动重写为：

- OpenAI function definition，或
- OpenAI Responses tool block，或
- Anthropic `tools` block，或
- Gemini `functionDeclarations`。

`llm_config` 中的 **`api_type`** 字段即为切换开关。修改该字段后，下游所有内容——协议格式、工具调用解析、流式事件——都会随之切换。

四个合法值：

| `api_type` | Provider | 特有配置 |
|---|---|---|
| `openai_chat_completion` | OpenAI Chat Completions 及任何兼容网关（Azure、OpenRouter、vLLM、Together、Groq……） | 默认值 |
| `openai_responses` | OpenAI Responses API（`o1`、`o3`、`gpt-5`） | `reasoning` block |
| `anthropic_chat_completion` | Anthropic Messages API | `thinking` block、prompt caching |
| `gemini_rest` | Google Generative Language REST API | `thinkingConfig` block |

## 当前起点

打开 `enterprise_data_agent/agent.yaml`，`llm_config` 当前状态：

```yaml
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: openai_chat_completion
  temperature: 0.2
  max_tokens: 4096
  stream: true
```

注意三个 `${env.*}` 占位符——这正是 YAML 在不同 Provider 之间保持稳定的关键：每个 Provider 唯一变化的只有 `.env` 文件。

先确认当前配置可以正常运行：

```bash
uv run enterprise_data_agent/start.py "海淀区有多少家企业？"
```

确认无误，开始切换 Provider。

## 6a —— 切换到 OpenAI Responses（推理模型）

Responses API 是 OpenAI 为 `o1` / `o3` / `gpt-5` 系列推理模型（reasoning model，会在回答前先在内部进行隐藏推理，只将结论返回给用户）提供的新端点。它与 Chat Completions 使用相同的认证和 base URL，但请求结构不同，并新增了 `reasoning` block 用于调节隐藏推理的强度。

**将 `llm_config` 修改为：**

```yaml
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: openai_responses
  max_tokens: 4096
  stream: true

  reasoning:
    effort: medium       # low | medium | high
    summary: detailed    # auto | concise | detailed
```

变更两处：

1. `api_type: openai_chat_completion` → `api_type: openai_responses`
2. 新增 `reasoning` block

注意此处**删除了 `temperature`**。推理模型会忽略该参数，部分 Responses-API 端点甚至会直接拒绝它。不删除也可运行（NexAU 有 `additional_drop_params` 后备机制），但保持配置整洁更佳。

| 字段 | 取值 | 用途 |
|---|---|---|
| `reasoning.effort` | `low`、`medium`、`high` | 模型可用的隐藏推理 token 额度 |
| `reasoning.summary` | `auto`、`concise`、`detailed` | 是否暴露推理总结及其详细程度 |

**更新 `.env`：**

```dotenv
LLM_MODEL=o3-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
```

**执行：**

```bash
uv run enterprise_data_agent/start.py "各 专精特新 等级有多少家企业？"
```

应看到与之前结构一致的答案。若使用 NexAU CLI 运行，还可在 trace 中看到 `reasoning` 总结块。

> NexAU 还处理了 Responses API 的一个微妙差异：当工具返回图片时，图片会嵌入**工具消息内部**，而非作为后续 user 消息注入。无需关心细节——工具 YAML 不变——但这正是同一个工具在两种 API 上均可运行而无需重写的原因。

## 6b —— 切换到 Anthropic Claude

现在切换到 Claude。不同的 Provider、不同的 base URL、不同的认证 header——但**Agent 本身不受影响**。

**修改 `llm_config`：**

```yaml
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: anthropic_chat_completion
  max_tokens: 16000
  stream: true

  thinking:
    type: adaptive       # adaptive | enabled
    budget_tokens: 2048
```

与上一段相比变更三处：

1. `api_type` 改为 `anthropic_chat_completion`
2. `max_tokens` 提升至 16000——Claude 的硬上限远高于 Chat Completions，extended thinking 也消耗该预算
3. `reasoning`（OpenAI 专有）替换为 `thinking`（Anthropic 专有）

| 字段 | 取值 | 用途 |
|---|---|---|
| `thinking.type` | `adaptive`、`enabled` | `adaptive` 由 Claude 自行决定是否进行推理;`enabled` 强制启用 |
| `thinking.budget_tokens` | int | Claude 隐藏推理的最大 token 额度 |

**更新 `.env`：**

```dotenv
LLM_MODEL=claude-sonnet-4-5
LLM_BASE_URL=https://api.anthropic.com
LLM_API_KEY=sk-ant-...
```

**执行：**

```bash
uv run enterprise_data_agent/start.py "AI 产业链里估值最高的 5 家企业是？"
```

该问题要求 Agent 关联 `enterprise_basic`、`enterprise_financing`、`industry_enterprise`、`industry` 四张表。观察 Claude 的选表策略——它同样依赖[第 3 章](./03-skills.md)中编写的 Skill 描述。

### 额外收益：prompt caching

Claude API 支持 prompt caching（提示词缓存：将每次不变的 system prompt + Skill 在服务端缓存，后续请求仅按增量计费，延迟也随之降低）。NexAU 用一个字段即可开启：

```yaml
llm_config:
  api_type: anthropic_chat_completion
  cache_control_ttl: 5m   # 将 system prompt + skills 缓存 5 分钟
  ...
```

对企业数据分析 Agent 而言意义显著——系统提示加 7 个 Skill 合计数千 token 且内容不变。缓存后首次调用全价，后续仅为零头。

## 6c —— 切换到 Google Gemini

同样的模式，切换 Provider。

**修改 `llm_config`：**

```yaml
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: gemini_rest
  max_tokens: 8192
  stream: true

  thinkingConfig:
    includeThoughts: true
    thinkingBudget: -1   # -1 = unlimited, 0 = disabled, >0 = token cap
```

结构已经熟悉：

1. `api_type: gemini_rest`
2. `thinking`（Anthropic）替换为 `thinkingConfig`（Gemini 专有字段名）
3. `max_tokens: 8192`——Gemini 的合理中位值

| 字段 | 取值 | 用途 |
|---|---|---|
| `thinkingConfig.includeThoughts` | bool | 响应中是否包含 thought 总结 |
| `thinkingConfig.thinkingBudget` | int | `-1` 不限、`0` 关闭、其他值为 token 上限 |

**更新 `.env`：**

```dotenv
LLM_MODEL=gemini-2.5-pro
LLM_BASE_URL=https://generativelanguage.googleapis.com
LLM_API_KEY=...
```

**执行：**

```bash
uv run enterprise_data_agent/start.py "哪条产业链的企业最多？"
```

NexAU 将工具 YAML 翻译为 Gemini `functionDeclarations`，将 `functionCall` parts 解析回来，然后执行循环。同一个 Agent，第三种协议。

## 6d —— 切换到自托管或第三方网关

并非每次都需要前沿 Provider。`openai_chat_completion` 之所以是默认值，是因为几乎所有第三方网关都支持该协议。以下为几个具体示例。

**Azure OpenAI：**

```yaml
llm_config:
  model: nex-agi/deepseek-v3.1-nex-1
  base_url: https://<resource>.openai.azure.com/openai/deployments/<deployment>
  api_key: ${env.AZURE_OPENAI_API_KEY}
  api_type: openai_chat_completion
```

**OpenRouter**（单一 key 访问多种模型）：

```yaml
llm_config:
  model: anthropic/claude-sonnet-4-5
  base_url: https://openrouter.ai/api/v1
  api_key: ${env.OPENROUTER_API_KEY}
  api_type: openai_chat_completion
```

**vLLM / 本地模型服务：**

```yaml
llm_config:
  model: meta-llama/Llama-3.1-70B-Instruct
  base_url: http://localhost:8000/v1
  api_key: not-used
  api_type: openai_chat_completion
```

**Groq：**

```yaml
llm_config:
  model: llama-3.3-70b-versatile
  base_url: https://api.groq.com/openai/v1
  api_key: ${env.GROQ_API_KEY}
  api_type: openai_chat_completion
```

以上均使用 `api_type: openai_chat_completion`——NexAU 分派的依据是协议格式，而非 URL 上的品牌。

## 工具调用的翻译机制

你只用 JSON Schema `input_schema` 编写过一次工具 YAML。以下是 NexAU 在不同 `api_type` 下如何处理它们：

| `api_type` | 出站工具格式 | 入站工具调用格式 |
|---|---|---|
| `openai_chat_completion` | OpenAI function definition | `tool_calls[].function.{name, arguments}` |
| `openai_responses` | Responses tool block | Responses tool-call item |
| `anthropic_chat_completion` | Anthropic `tools` 数组 | `tool_use` content block |
| `gemini_rest` | Gemini `functionDeclarations` | `functionCall` part |

无需关心这些细节——但了解该表的存在，在调试模型工具调用异常时十分有用：问题几乎总是出在描述中，而非协议格式上。

## `tool_call_mode: xml`

我们在 `agent.yaml` 中设置了 `tool_call_mode: structured`，使用上表中 Provider 原生的 function calling（模型在 API 层面返回结构化 JSON 表示"要调用哪个工具、参数是什么"，而非混在普通文本中自行解析）。另一个选项是：

```yaml
tool_call_mode: xml
```

`xml` 模式完全绕开 Provider 原生的 function calling。NexAU 将工具格式化为 prompt 中的 XML，然后从模型的文本输出中解析 XML。适用场景：

- 运行不支持原生 function calling 的模型（旧版开源模型、base 模型……）
- 需要精确控制工具调用的 prompt
- 调试工具调用回归问题，需要查看原始文本

`xml` 路径在所有四种 `api_type` 上均可运行，因此可作为统一的 fallback 方案。

## 本章小结

通过编辑一个配置块，已将同一个企业数据分析 Agent 运行在四种协议上。心智模型如下：

- **`api_type`** 决定协议格式
- **`tool_call_mode`** 决定使用 Provider 原生 function calling 还是 NexAU 中性 XML
- **`reasoning` / `thinking` / `thinkingConfig`** 是推理模型的 Provider 专有配置——选与 `api_type` 匹配的即可
- **其他所有内容**（工具、Skill、系统提示、中间件）均保持不变

这种可移植性并非无代价——NexAU 需要维护四套翻译器——但对 Agent 开发者而言，这意味着可以为具体任务选择最合适的模型而无需重写任何代码。

## 通过 Python 代码配置

上述所有字段同样可在 `LLMConfig` 类上设置，适用于以代码而非 YAML 构建的场景：

```python
from nexau import LLMConfig

cfg = LLMConfig(
    model="claude-sonnet-4-5",
    base_url="https://api.anthropic.com",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    api_type="anthropic_chat_completion",
    max_tokens=16000,
    stream=True,
    # Provider 专有配置通过 **kwargs 流入 extra_params
    thinking={"type": "adaptive", "budget_tokens": 2048},
)
```

任何未识别的 keyword 参数都会存入 `extra_params` 并原样转发——这与 YAML loader 处理 `reasoning`、`thinking`、`thinkingConfig` 的机制完全一致。

## 后续方向

至此，你的 Agent 已经具备：

- 通过手写的、有 schema 校验的工具与真实数据库交互
- 将每张表的领域知识封装在独立的 Skill 中
- 修改一个配置块即可运行在四种 LLM 协议上

这就是完整的 0 → 1 教程。从这里出发，自然的下一步包括：

- **添加子 Agent** 处理特定子任务（如"schema-explorer"：仅配备 schema 查询工具与独立上下文预算）
- **接入 MCP server**（MCP = Model Context Protocol，Anthropic 提出的工具协议标准，可将任何支持 MCP 的工具/服务一键接入 Agent）
- **接入 tracer**（`nexau.archs.tracer.adapters.langfuse:LangfuseTracer`）建立可观测性
- **迭代 Skill。** Agent 的质量几乎完全依赖 Skill 的持续完善——每个错误查询都可转化为一条新的 "Gotchas"

框架部分已经完备。剩下的是 Skill 层面的提示工程——那才是真正做产品的地方。
