# LLM API types

This is **Step 4**. In [Step 3](./get-started/agent-yaml.md) you got the NL2SQL agent answering questions on OpenAI. Now we're going to take that exact same `agent.yaml` — same tools, same skills, same system prompt — and run it on **OpenAI Responses**, **Anthropic Claude**, and **Google Gemini**, by editing only the `llm_config` block.

The goal of this page is for you to *type each block by hand* and feel how little has to change. By the end you'll have run the same agent on four different wire formats.

## Why this works

NexAU's job is translation. You wrote one set of `*.tool.yaml` files in [Step 1](./get-started/tool-yaml.md). At runtime, depending on `api_type`, NexAU rewrites those JSON Schemas into:

- OpenAI function definitions, or
- OpenAI Responses tool blocks, or
- Anthropic `tools` blocks, or
- Gemini `functionDeclarations`.

The **`api_type`** field on `llm_config` is the switch. Change it, and everything downstream — the wire format, the tool-call parsing, the streaming events — switches with it.

There are four valid values:

| `api_type` | Provider | Notable extras |
|---|---|---|
| `openai_chat_completion` | OpenAI Chat Completions and any compatible gateway (Azure, OpenRouter, vLLM, Together, Groq…) | The default |
| `openai_responses` | OpenAI Responses API (`o1`, `o3`, `gpt-5`) | `reasoning` block |
| `anthropic_chat_completion` | Anthropic Messages API | `thinking` block, prompt caching |
| `gemini_rest` | Google Generative Language REST API | `thinkingConfig` block |

## Where we're starting

Open `nl2sql_agent/agent.yaml`. The `llm_config` block currently looks like this:

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

Notice the three `${env.*}` placeholders. They're how we'll keep the YAML stable across providers — the only thing that changes per provider is your `.env`.

Run the agent once to confirm it still works:

```bash
dotenv run uv run nl2sql_agent/start.py "How many enterprises are in 海淀区?"
```

Good. Now let's swap providers.

## Step 4a — switch to OpenAI Responses (reasoning models)

The Responses API is OpenAI's newer endpoint for the `o1` / `o3` / `gpt-5` family. It has the same authentication and base URL as Chat Completions, but a different request shape and a `reasoning` block that lets you tune how much hidden thinking the model spends.

**Edit `llm_config` to look like this:**

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

Two things changed:

1. `api_type: openai_chat_completion` → `api_type: openai_responses`
2. Added a `reasoning` block

Notice we **dropped `temperature`**. Reasoning models ignore it, and some Responses-API endpoints reject the parameter outright. You don't need to remove it — NexAU has a `additional_drop_params` escape hatch — but it's cleaner to omit fields the model won't use.

| Field | Values | Purpose |
|---|---|---|
| `reasoning.effort` | `low`, `medium`, `high` | How many hidden reasoning tokens the model is allowed to spend |
| `reasoning.summary` | `auto`, `concise`, `detailed` | Whether and how to surface a reasoning summary |

**Update your `.env`:**

```dotenv
LLM_MODEL=o3-mini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
```

**Run it:**

```bash
dotenv run uv run nl2sql_agent/start.py "How many enterprises in each 专精特新 level?"
```

You should see the same answer shape as before, possibly with a `reasoning` summary block in the trace if you're using the CLI (`./run-agent nl2sql_agent/agent.yaml`).

> NexAU also handles a subtle Responses-API quirk: when a tool returns an image, the image is embedded **inside the tool message** rather than injected as a follow-up user message. You don't have to think about this — your tool YAML stays the same — but it's why the same tool works on both APIs without rewrites.

## Step 4b — switch to Anthropic Claude

Now Claude. Different provider, different base URL, different auth header — but the *agent* doesn't care.

**Edit `llm_config`:**

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

Three things changed from the previous block:

1. `api_type` is now `anthropic_chat_completion`
2. `max_tokens` bumped to 16000 — Claude's hard cap is much higher than Chat Completions, and extended thinking eats from this budget
3. `reasoning` (OpenAI-only) replaced with `thinking` (Anthropic-only)

| Field | Values | Purpose |
|---|---|---|
| `thinking.type` | `adaptive`, `enabled` | `adaptive` lets Claude decide whether to think; `enabled` always thinks |
| `thinking.budget_tokens` | integer | Max tokens Claude can spend on hidden thinking |

**Update your `.env`:**

```dotenv
LLM_MODEL=claude-sonnet-4-5
LLM_BASE_URL=https://api.anthropic.com
LLM_API_KEY=sk-ant-...
```

**Run it:**

```bash
dotenv run uv run nl2sql_agent/start.py "Show the top 5 enterprises by valuation in the AI industry chain"
```

This question forces the agent to join `enterprise_basic`, `enterprise_financing`, `industry_enterprise`, and `industry`. Watch how Claude picks tables — it'll lean on the skill descriptions you wrote in [Step 2](./get-started/skills.md) just like OpenAI did.

### A nice extra: prompt caching

Claude's API supports prompt caching, and NexAU exposes it via a single field:

```yaml
llm_config:
  api_type: anthropic_chat_completion
  cache_control_ttl: 5m   # cache the system prompt + skills for 5 minutes
  ...
```

For an NL2SQL agent this is a meaningful win — the system prompt plus all 7 skills add up to several thousand tokens that don't change between turns. Caching them means you pay full price for the first call and a fraction afterward.

## Step 4c — switch to Google Gemini

Same drill, different provider.

**Edit `llm_config`:**

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

The shape is starting to feel familiar:

1. `api_type: gemini_rest`
2. `thinking` (Anthropic) replaced with `thinkingConfig` (Gemini's exact field name)
3. `max_tokens: 8192` — Gemini's reasonable middle ground

| Field | Values | Purpose |
|---|---|---|
| `thinkingConfig.includeThoughts` | bool | Whether thought summaries come back in the response |
| `thinkingConfig.thinkingBudget` | int | `-1` unlimited, `0` disabled, otherwise a token cap |

**Update your `.env`:**

```dotenv
LLM_MODEL=gemini-2.5-pro
LLM_BASE_URL=https://generativelanguage.googleapis.com
LLM_API_KEY=...
```

**Run it:**

```bash
dotenv run uv run nl2sql_agent/start.py "Which industry chain has the most enterprises?"
```

NexAU translates your tool YAMLs to Gemini `functionDeclarations`, parses `functionCall` parts back out, and runs the loop. Same agent, third wire format.

## Step 4d — switch to a self-hosted or third-party gateway

You don't always need a frontier provider. The original `openai_chat_completion` is the default precisely because almost every other gateway speaks it. Here are concrete examples — try one if you have it running locally.

**Azure OpenAI:**

```yaml
llm_config:
  model: gpt-4o
  base_url: https://<resource>.openai.azure.com/openai/deployments/<deployment>
  api_key: ${env.AZURE_OPENAI_API_KEY}
  api_type: openai_chat_completion
```

**OpenRouter** (one key, many models):

```yaml
llm_config:
  model: anthropic/claude-sonnet-4-5
  base_url: https://openrouter.ai/api/v1
  api_key: ${env.OPENROUTER_API_KEY}
  api_type: openai_chat_completion
```

**vLLM / local model server:**

```yaml
llm_config:
  model: meta-llama/Llama-3.1-70B-Instruct
  base_url: http://localhost:8000/v1
  api_key: not-used
  api_type: openai_chat_completion
```

**Groq:**

```yaml
llm_config:
  model: llama-3.3-70b-versatile
  base_url: https://api.groq.com/openai/v1
  api_key: ${env.GROQ_API_KEY}
  api_type: openai_chat_completion
```

All of these still have `api_type: openai_chat_completion` — the wire format is what NexAU dispatches on, not the brand name on the URL.

## How tool calls get translated

You wrote your tool YAMLs once with JSON Schema `input_schema`. Here's what NexAU does with them per `api_type`:

| `api_type` | Outbound tool format | Inbound tool-call format |
|---|---|---|
| `openai_chat_completion` | OpenAI function definitions | `tool_calls[].function.{name, arguments}` |
| `openai_responses` | Responses tool blocks | Responses tool-call items |
| `anthropic_chat_completion` | Anthropic `tools` array | `tool_use` content blocks |
| `gemini_rest` | Gemini `functionDeclarations` | `functionCall` parts |

You don't have to think about any of this — but knowing the table exists is useful when you're debugging a model that's calling tools wrong: the bug is almost always in the description, not in the wire format.

## What about `tool_call_mode: xml`?

In `agent.yaml` we set `tool_call_mode: structured`, which uses each provider's native function-calling format from the table above. The alternative is:

```yaml
tool_call_mode: xml
```

`xml` mode bypasses the provider's native function calling entirely. NexAU formats your tools as XML in the prompt and parses XML out of the model's text output. Use it when:

- You're running a model that doesn't have native function calling (older open-source models, base models, …)
- You want exact control over the tool-call prompt
- You're debugging a tool-call regression and want to see the raw text

The `xml` path works on all four `api_type` values, so it's a uniform fallback.

## What you've learned

You've now run the same NL2SQL agent across four wire formats by editing one block. The mental model is:

- **`api_type`** decides the wire format
- **`tool_call_mode`** decides whether to use the provider's native function calling or NexAU's neutral XML
- **`reasoning` / `thinking` / `thinkingConfig`** are provider-specific blocks for reasoning models — pick the one that matches your `api_type`
- **Everything else** (tools, skills, system prompt, middlewares) is untouched

The portability isn't free — NexAU has to maintain four translators — but for *you*, the agent author, it means you can pick the best model for the job without rewriting anything.

## From Python

Everything above is also available from the `LLMConfig` class directly, in case you're building the agent programmatically rather than from YAML:

```python
from nexau import LLMConfig

cfg = LLMConfig(
    model="claude-sonnet-4-5",
    base_url="https://api.anthropic.com",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    api_type="anthropic_chat_completion",
    max_tokens=16000,
    stream=True,
    # provider-specific extras flow through **kwargs and land on extra_params
    thinking={"type": "adaptive", "budget_tokens": 2048},
)
```

Any unknown keyword arguments are stored on `extra_params` and forwarded verbatim — that's the same mechanism the YAML loader uses for `reasoning`, `thinking`, and `thinkingConfig`.

## Where to go next

You now have an agent that:

- Talks to a real database through hand-written, schema-validated tools
- Carries one Skill per table as long-term knowledge
- Runs on any of four LLM wire formats with a one-block edit

That's the full "0 → 1" tutorial. From here, the natural next steps are:

- **Add a sub-agent** for a specialized sub-task (e.g. a "schema-explorer" with read-only schema tools and a separate context budget). See `examples/code_agent/sub_agent.yaml` in the source repo.
- **Add an MCP server** to pull in tools from outside the project.
- **Add a tracer** (`nexau.archs.tracer.adapters.langfuse:LangfuseTracer`) once you start needing observability.
- **Iterate on the skills.** The agent's quality grows almost entirely through skill edits — every wrong query becomes a new "Gotchas" entry.

The harness has done its job. The rest is prompt engineering on the skills, and that's where the real product work happens.
