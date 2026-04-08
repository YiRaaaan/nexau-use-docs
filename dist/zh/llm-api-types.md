# 第 6 章 · 跨 Provider 运行

前面 5 章你已经把企业数据分析 Agent 跑起来了——但只在 OpenAI Chat Completions 协议上。第 6 章不再加新功能，只回答一个问题：**已经写好的这一份 `agent.yaml`（同样的工具、同样的 Skill、同样的系统提示），怎么换到 Anthropic Claude / Google Gemini / OpenAI Responses 上跑?**

答案是：**只改 `llm_config` 这一块**，其他什么都不动。

## 为什么这能成

NexAU 的工作之一就是翻译。你在第 2 章写了一份 `ExecuteSQL.tool.yaml`，运行时 NexAU 根据 `api_type` 把里面的 JSON Schema 重写成：

- OpenAI function definition，或者
- OpenAI Responses tool block，或者
- Anthropic `tools` block，或者
- Gemini `functionDeclarations`。

`llm_config` 上的 **`api_type`** 字段就是开关。改了它，下游所有东西 —— 协议格式、工具调用解析、流式事件 —— 都跟着切换。

四个合法值：

| `api_type` | Provider | 特有 extra |
|---|---|---|
| `openai_chat_completion` | OpenAI Chat Completions 和任何兼容网关（Azure、OpenRouter、vLLM、Together、Groq...） | 默认 |
| `openai_responses` | OpenAI Responses API（`o1`、`o3`、`gpt-5`） | `reasoning` block |
| `anthropic_chat_completion` | Anthropic Messages API | `thinking` block、prompt caching |
| `gemini_rest` | Google Generative Language REST API | `thinkingConfig` block |

## 我们的起点

打开 `enterprise_data_agent/agent.yaml`。`llm_config` 现在长这样：

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

注意三个 `${env.*}` 占位符。这就是我们让 YAML 在不同 Provider 之间保持稳定的方式 —— 每个 Provider 唯一变的就是你的 `.env`。

先跑一遍确认它还能用：

```bash
uv run enterprise_data_agent/start.py "海淀区有多少家企业？"
```

OK，开始换 Provider。

## 6a —— 切换到 OpenAI Responses （推理模型）

Responses API 是 OpenAI 给 `o1` / `o3` / `gpt-5` 系列推理模型（reasoning model，会在回答前先在内部"想一会儿"，把推理过程藏起来，只把结论给你）用的新端点。它跟 Chat Completions 用一样的认证和 base URL，但请求结构不同，并且多了一个 `reasoning` block，让你调节模型用多少隐藏推理。

**把 `llm_config` 改成这样：**

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

变了两个东西：

1. `api_type: openai_chat_completion` → `api_type: openai_responses`
2. 多了一个 `reasoning` block

注意我们 **去掉了 `temperature`**。推理模型忽略它，有些 Responses-API 端点甚至会直接拒绝这个参数。你不删也行 —— NexAU 有 `additional_drop_params` 后门 —— 但保持干净更好。

| 字段 | 取值 | 用途 |
|---|---|---|
| `reasoning.effort` | `low`、`medium`、`high` | 模型可以花多少隐藏推理 token |
| `reasoning.summary` | `auto`、`concise`、`detailed` | 是否暴露推理总结、以及多详细 |

**更新 `.env`：**

```dotenv
LLM_MODEL=o3-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
```

**跑：**

```bash
uv run enterprise_data_agent/start.py "各 专精特新 等级有多少家企业？"
```

应该看到跟之前形状一样的答案，如果你用 CLI（`./run-agent enterprise_data_agent/agent.yaml`）还能在 trace 里看到 `reasoning` 总结块。

> NexAU 还处理了 Responses API 的一个微妙差异：当工具返回图片时，图片会嵌在**工具消息内部**，而不是作为后续 user 消息注入。你不用关心这个 —— 你的工具 YAML 不变 —— 但这正是同一个工具在两种 API 上都能跑而不用重写的原因。

## 6b —— 切换到 Anthropic Claude

现在换 Claude。不同的 Provider，不同的 base URL，不同的认证 header —— 但 **智能体不在乎**。

**改 `llm_config`：**

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

跟上一段比变了三个东西：

1. `api_type` 现在是 `anthropic_chat_completion`
2. `max_tokens` 提到 16000 —— Claude 的硬上限比 Chat Completions 高得多，extended thinking 也吃这个预算
3. `reasoning`（OpenAI 专有）换成 `thinking`（Anthropic 专有）

| 字段 | 取值 | 用途 |
|---|---|---|
| `thinking.type` | `adaptive`、`enabled` | `adaptive` 让 Claude 自己决定要不要想；`enabled` 永远想 |
| `thinking.budget_tokens` | int | Claude 隐藏推理可以花的最多 token |

**更新 `.env`：**

```dotenv
LLM_MODEL=claude-sonnet-4-5
LLM_BASE_URL=https://api.anthropic.com
LLM_API_KEY=sk-ant-...
```

**跑：**

```bash
uv run enterprise_data_agent/start.py "AI 产业链里估值最高的 5 家企业是？"
```

这个问题强迫智能体 join `enterprise_basic`、`enterprise_financing`、`industry_enterprise`、`industry`。看 Claude 怎么挑表——它会跟 OpenAI 一样依赖你在[第 3 章](./03-skills.md)写的 Skill 描述。

### 一个额外的好东西：prompt caching

Claude API 支持 prompt caching（提示词缓存，把每次都不变的那段 system prompt + Skill 在服务端缓存住，后续请求只算增量部分的钱、延迟也低很多），NexAU 用一个字段就能开：

```yaml
llm_config:
  api_type: anthropic_chat_completion
  cache_control_ttl: 5m   # 把 system prompt + skills 缓存 5 分钟
  ...
```

对企业数据分析 Agent 这意义不小 —— 系统提示加 7 个 Skill 加起来好几千 token 是不变的。缓存它们意味着第一次调用是全价，之后只是零头。

## 6c —— 切换到 Google Gemini

同样的套路，换个 Provider。

**改 `llm_config`：**

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

形状已经熟悉了：

1. `api_type: gemini_rest`
2. `thinking`（Anthropic）换成 `thinkingConfig`（Gemini 自己的字段名）
3. `max_tokens: 8192` —— Gemini 的合理中位数

| 字段 | 取值 | 用途 |
|---|---|---|
| `thinkingConfig.includeThoughts` | bool | 响应里是否包含 thought 总结 |
| `thinkingConfig.thinkingBudget` | int | `-1` 不限、`0` 关闭、其他为 token 上限 |

**更新 `.env`：**

```dotenv
LLM_MODEL=gemini-2.5-pro
LLM_BASE_URL=https://generativelanguage.googleapis.com
LLM_API_KEY=...
```

**跑：**

```bash
uv run enterprise_data_agent/start.py "哪条产业链的企业最多？"
```

NexAU 把你的工具 YAML 翻译成 Gemini `functionDeclarations`，把 `functionCall` parts 解析回来，然后跑循环。同一个智能体，第三种协议。

## 6d —— 切到自托管或第三方网关

不是每次都需要前沿 Provider。`openai_chat_completion` 之所以是默认值，是因为几乎每个第三方网关都讲这套协议。下面是几个具体例子 —— 你本地有就试试。

**Azure OpenAI：**

```yaml
llm_config:
  model: nex-agi/deepseek-v3.1-nex-1
  base_url: https://<resource>.openai.azure.com/openai/deployments/<deployment>
  api_key: ${env.AZURE_OPENAI_API_KEY}
  api_type: openai_chat_completion
```

**OpenRouter**（一个 key，多种模型）：

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

这些都还是 `api_type: openai_chat_completion` —— NexAU dispatch 的是协议格式，不是 URL 上的品牌。

## 工具调用是怎么翻译的

你只用 JSON Schema `input_schema` 写过一次工具 YAML。下面是 NexAU 在不同 `api_type` 下用它们做的事：

| `api_type` | 出站工具格式 | 入站工具调用格式 |
|---|---|---|
| `openai_chat_completion` | OpenAI function definition | `tool_calls[].function.{name, arguments}` |
| `openai_responses` | Responses tool block | Responses tool-call item |
| `anthropic_chat_completion` | Anthropic `tools` 数组 | `tool_use` content block |
| `gemini_rest` | Gemini `functionDeclarations` | `functionCall` part |

你完全不用关心这些 —— 但知道这张表存在，在调试模型工具调用错误的时候很有用：bug 几乎总是在描述里，不在协议格式里。

## 那 `tool_call_mode: xml` 呢?

我们在 `agent.yaml` 里设了 `tool_call_mode: structured`，用上表里 Provider 原生的 function calling（模型在 API 层面返回一个结构化 JSON 表示"我要调哪个工具、参数是什么"，而不是混在普通文本里让你 parse）。另一个选项是：

```yaml
tool_call_mode: xml
```

`xml` 模式完全绕开 Provider 原生的 function calling。NexAU 把工具格式化成 prompt 里的 XML，然后从模型的文本输出里解析 XML。什么时候用：

- 跑没有原生 function calling 的模型（老的开源模型、base 模型...）
- 想精确控制工具调用的 prompt
- 调试工具调用 regression，想看原始文本

`xml` 路径在所有四种 `api_type` 上都能跑，所以是一个统一的 fallback。

## 你学到了什么

你已经通过编辑一个 block 把同一个企业数据分析 Agent 跑过四种协议了。心智模型是：

- **`api_type`** 决定协议格式
- **`tool_call_mode`** 决定用 Provider 原生 function calling 还是 NexAU 中性 XML
- **`reasoning` / `thinking` / `thinkingConfig`** 是推理模型的 Provider 专有 block —— 选跟你的 `api_type` 匹配的那个
- **其他所有东西**（工具、Skill、系统提示、中间件）都不动

这种可移植性不是免费的 —— NexAU 要维护四套翻译器 —— 但对**你**这个智能体作者来说，意味着你可以为活儿挑最合适的模型，什么都不用重写。

## 从 Python

上面这些字段也都在 `LLMConfig` 类上，万一你用代码而不是 YAML 来构建：

```python
from nexau import LLMConfig

cfg = LLMConfig(
    model="claude-sonnet-4-5",
    base_url="https://api.anthropic.com",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    api_type="anthropic_chat_completion",
    max_tokens=16000,
    stream=True,
    # Provider 专有的 extras 通过 **kwargs 流到 extra_params 上
    thinking={"type": "adaptive", "budget_tokens": 2048},
)
```

任何未知的 keyword 都会被存到 `extra_params` 上原样转发 —— 这就是 YAML loader 处理 `reasoning`、`thinking`、`thinkingConfig` 用的同一个机制。

## 接下来去哪儿

你现在的智能体：

- 通过手写的、有 schema 校验的工具跟真实数据库说话
- 把每张表的长期知识装在一个 Skill 里
- 改一个 block 就能跑在四种 LLM 协议上

这就是完整的 0 → 1 教程。从这里开始，自然的下一步是：

- **加一个子智能体**处理某个特化子任务（比如一个"schema-explorer"，只读 schema 工具加独立上下文预算）。源仓库的 `examples/code_agent/sub_agent.yaml` 有例子。
- **加一个 MCP server**（MCP = Model Context Protocol，Anthropic 提出的一个工具协议，让任何支持 MCP 的工具/服务可以一键接到智能体上）把项目外的工具拉进来。
- **加一个 tracer**（`nexau.archs.tracer.adapters.langfuse:LangfuseTracer`）当你开始需要可观测性。
- **迭代 Skill。** 智能体的质量几乎完全靠 Skill 的编辑增长 —— 每个错的查询都变成一条新的 "Gotchas"。

框架的活儿干完了。剩下的是 Skill 上的提示工程，那才是真正做产品的地方。
