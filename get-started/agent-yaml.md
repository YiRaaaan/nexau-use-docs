# Writing the agent YAML

This is **Step 3**. We have tools and we have skills — now we write the file that ties them together. By the end of this page you'll have a runnable `agent.yaml`, a `system_prompt.md`, and a `start.py`. You'll be able to ask the agent questions about the database.

## The shape of an agent.yaml

An agent YAML always has the same shape: a top-level type/name/prompt block, an `llm_config` for the model, and then optional lists of `tools`, `skills`, `sub_agents`, `mcp_servers`, `middlewares`, and `tracers`. Here is the smallest valid file:

```yaml
type: agent
name: nl2sql_agent
system_prompt: You answer questions about a SQLite database.

llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: openai_chat_completion
```

That works, but it doesn't know about our tools or skills. Let's grow it.

## Step 3a — write the system prompt first

The system prompt tells the agent how to behave. For an NL2SQL agent there are a few things every workflow needs: read the relevant skill, prefer narrow queries, always include a LIMIT, return the SQL alongside the answer.

Create `nl2sql_agent/system_prompt.md`:

```markdown
You are an NL2SQL agent for the **North Nova enterprise intelligence database** —
a SQLite mirror of seven core tables describing Chinese enterprises, their
contacts, financing status, products, and the industry chains they belong to.

Your job is to translate the user's natural-language questions about this
database into correct SQL, execute the query, and return a clear answer
grounded in the actual rows.

## Database

- Engine: SQLite (read-only)
- Tables: `enterprise_basic`, `enterprise_contact`, `enterprise_financing`,
  `enterprise_product`, `industry`, `industry_enterprise`, `users`
- Primary join key across the `enterprise_*` tables: `credit_code`

Detailed business semantics, column descriptions, and example queries for
each table are provided as **Skills** — one skill per table. Read the
relevant skill before writing a query.

## Workflow

For every user question, follow this loop:

1. **Plan.** Identify which tables are needed and in what order.
2. **Inspect when uncertain.** Call `list_tables` or `describe_table` if
   you're unsure about column names.
3. **Write the SQL.** SQLite syntax. Always include a `LIMIT`. Prefer
   explicit column lists over `SELECT *`. Join `enterprise_*` on `credit_code`.
4. **Execute.** Call `sql_query`.
5. **Verify.** If the result is empty or surprising, double-check column
   names and value formats.
6. **Answer.** Reply in the user's language with a concise, direct answer
   grounded in the actual rows. Include the SQL you ran in a code block at
   the end of your message.

## Constraints

- Read-only. Only `SELECT` and `WITH ... SELECT` are allowed.
- No hallucinated columns. If a column doesn't exist, say so explicitly.
- Be honest about limits — this is a 50-row sample per table, not the full
  production database.
- Personal-identifier fields are redacted in this mock.

## Output format

End every successful answer with a fenced SQL block.
```

A few things to notice:

- **The system prompt does not duplicate the skills.** It points the model at them ("Read the relevant skill before writing a query"). Each skill carries its own column-level knowledge; the system prompt only carries agent-wide rules.
- **The workflow is a numbered loop.** Models follow numbered lists better than they follow prose. State the steps and the order.
- **Constraints are explicit.** Read-only, no hallucinated columns, be honest about sample size. Saying these once in the system prompt is more reliable than hoping the model figures them out.

The full file lives at [`nl2sql_agent/system_prompt.md`](../nl2sql_agent/system_prompt.md).

## Step 3b — write the agent.yaml

Now the main file. Create `nl2sql_agent/agent.yaml`:

```yaml
type: agent
name: nl2sql_agent
description: NL2SQL agent over the North Nova enterprise SQLite mirror.
max_context_tokens: 200000
max_iterations: 50

system_prompt: ./system_prompt.md
system_prompt_type: jinja
tool_call_mode: structured

llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
  api_type: openai_chat_completion
  temperature: 0.2
  max_tokens: 4096
  stream: true

tools:
  # Schema discovery — cheap, read-only, no SQL needed
  - name: list_tables
    yaml_path: ./tools/list_tables.tool.yaml
    binding: nl2sql_agent.bindings:list_tables

  - name: describe_table
    yaml_path: ./tools/describe_table.tool.yaml
    binding: nl2sql_agent.bindings:describe_table

  # The actual SELECT executor
  - name: sql_query
    yaml_path: ./tools/sql_query.tool.yaml
    binding: nl2sql_agent.bindings:sql_query

# One skill per table — the model's authoritative knowledge of the schema,
# business semantics, common values, and example queries.
skills:
  - ./skills/enterprise_basic
  - ./skills/enterprise_contact
  - ./skills/enterprise_financing
  - ./skills/enterprise_product
  - ./skills/industry
  - ./skills/industry_enterprise
  - ./skills/users

middlewares:
  # Truncate huge query results so a single SELECT * can't blow the context.
  - import: nexau.archs.main_sub.execution.middleware.long_tool_output:LongToolOutputMiddleware
    params:
      max_output_chars: 8000
      head_lines: 30
      tail_lines: 10
      head_chars: 4000
      tail_chars: 2000
```

Let's walk through every block.

### Top-level fields

```yaml
type: agent
name: nl2sql_agent
description: NL2SQL agent over the North Nova enterprise SQLite mirror.
max_context_tokens: 200000
max_iterations: 50
```

| Field | Purpose |
|---|---|
| `type` | Always `agent`. Distinguishes from `*.tool.yaml`. |
| `name` | Used in logs, traces, and as the default trace name. |
| `description` | Free-form. Surfaces in the CLI and debugger. |
| `max_context_tokens` | Hard ceiling on the context window. Used by context-compaction middleware as well. |
| `max_iterations` | Tool-calling loop budget. NL2SQL questions usually finish in 3–8 iterations; 50 is a generous safety net. |

### `system_prompt` and `tool_call_mode`

```yaml
system_prompt: ./system_prompt.md
system_prompt_type: jinja
tool_call_mode: structured
```

- `system_prompt` can be either an inline string or a path to a markdown file. We use a file because it's longer than fits in YAML and easier to edit.
- `system_prompt_type: jinja` means the file is rendered as a Jinja2 template. Variables come from whatever you pass as `context=` to `agent.run(...)`. We don't have any template variables yet, but the option costs nothing.
- `tool_call_mode: structured` uses the provider's native function-calling format. NexAU translates our tool schemas to the right wire format based on `llm_config.api_type` — that's how the same agent works on OpenAI and Anthropic and Gemini. The alternative is `xml`, used for models without native function calling.

### `llm_config` — the model

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

This block is the only thing you'd change to swap providers. Walk through it:

| Field | What it does |
|---|---|
| `model` | The provider's model id. `${env.LLM_MODEL}` lets the same file work across environments. |
| `base_url` | Provider endpoint. NexAU is OpenAI-SDK-compatible by default, so any OpenAI-compatible gateway (Azure, OpenRouter, vLLM, …) works. |
| `api_key` | API key, from env. |
| `api_type` | The wire format. `openai_chat_completion` is the default. The four supported values are `openai_chat_completion`, `openai_responses`, `anthropic_chat_completion`, and `gemini_rest`. |
| `temperature: 0.2` | NL2SQL benefits from low temperature — we want deterministic, conservative SQL. |
| `max_tokens: 4096` | Per-response cap. Plenty for an SQL answer. |
| `stream: true` | Stream the response so the CLI feels fast. |

For all four `api_type` values and how to switch between them, see [LLM API types](../llm-api-types.md). We rerun the same agent on three providers there.

### `tools`

```yaml
tools:
  - name: list_tables
    yaml_path: ./tools/list_tables.tool.yaml
    binding: nl2sql_agent.bindings:list_tables

  - name: describe_table
    yaml_path: ./tools/describe_table.tool.yaml
    binding: nl2sql_agent.bindings:describe_table

  - name: sql_query
    yaml_path: ./tools/sql_query.tool.yaml
    binding: nl2sql_agent.bindings:sql_query
```

Each entry has three fields:

- `name` — what the model calls. Should match the tool YAML's `name`.
- `yaml_path` — the schema, relative to `agent.yaml`.
- `binding` — `module.path:callable` import string for the Python implementation.

This is where the two halves we wrote in [Step 1](./tool-yaml.md) get glued together. NexAU loads the schema, imports the binding, and registers them as a single tool.

The order of tools doesn't affect behavior, but listing schema-discovery tools before the executor (`list_tables` → `describe_table` → `sql_query`) is a small visual cue that matches the workflow in the system prompt.

### `skills`

```yaml
skills:
  - ./skills/enterprise_basic
  - ./skills/enterprise_contact
  - ./skills/enterprise_financing
  - ./skills/enterprise_product
  - ./skills/industry
  - ./skills/industry_enterprise
  - ./skills/users
```

Each entry is a folder path relative to `agent.yaml`. NexAU walks each folder, reads `SKILL.md`, parses the frontmatter, and injects the body into the agent's context at startup. See [Step 2](./skills.md) for the format.

### `middlewares`

```yaml
middlewares:
  - import: nexau.archs.main_sub.execution.middleware.long_tool_output:LongToolOutputMiddleware
    params:
      max_output_chars: 8000
      head_lines: 30
      tail_lines: 10
      head_chars: 4000
      tail_chars: 2000
```

Middlewares hook into the agent loop. `LongToolOutputMiddleware` catches tool results above `max_output_chars` and replaces the middle with a "(truncated)" marker, keeping `head_lines` from the top and `tail_lines` from the bottom.

For an NL2SQL agent this is a real safety net: if the model writes `SELECT * FROM enterprise_basic` and forgets a `LIMIT`, that's 50 rows × ~30 columns of mostly empty fields — easily 50KB of JSON. The middleware truncates it to ~8KB before it reaches the model's context.

You can stack middlewares. Other useful ones include:

- `nexau.archs.main_sub.execution.middleware.context_compaction:ContextCompactionMiddleware` — auto-summarize context once it crosses a fraction of `max_context_tokens`. Useful for long sessions.
- `nexau.archs.main_sub.execution.hooks:LoggingMiddleware` — log every model call and tool call.

Each entry is `{import: module:Class, params: {...}}`. The import string is the same `module:Class` form used by tool bindings.

### What we left out (for now)

The `agent.yaml` above does not include:

- **`sub_agents`** — for delegating to specialized children. We don't need that yet, but for example you could spin up a "schema-explorer" sub-agent with read-only schema tools and a separate context budget. See the source repo's `examples/code_agent/sub_agent.yaml`.
- **`mcp_servers`** — for pulling in tools from MCP servers. Useful if you want to give the agent access to external services alongside the SQL tools.
- **`tracers`** — for forwarding execution data to Langfuse or similar. Add one when you start needing observability:

  ```yaml
  tracers:
    - import: nexau.archs.tracer.adapters.langfuse:LangfuseTracer
      params:
        public_key: ${env.LANGFUSE_PUBLIC_KEY}
        secret_key: ${env.LANGFUSE_SECRET_KEY}
        host: ${env.LANGFUSE_HOST}
  ```

You can add any of these to `agent.yaml` later without restructuring anything.

## Step 3c — write the entry point

You can already run the agent with the NexAU CLI:

```bash
./run-agent nl2sql_agent/agent.yaml
```

But for embedding in another app, write a Python entry point. Create `nl2sql_agent/start.py`:

```python
"""Entry point for the NL2SQL agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from nexau import Agent, AgentConfig

HERE = Path(__file__).resolve().parent

# Make sure tool bindings (`nl2sql_agent.bindings:...`) resolve when running
# the script directly without installing this directory as a package.
sys.path.insert(0, str(HERE.parent))

# Default the SQLite path to mock.sqlite next to this folder.
os.environ.setdefault("NL2SQL_DB_PATH", str(HERE.parent / "mock.sqlite"))


def main() -> None:
    config = AgentConfig.from_yaml(HERE / "agent.yaml")
    agent = Agent(config=config)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(agent.run(question))
        return

    print("NL2SQL agent ready. Type a question (Ctrl-D to exit).")
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            print()
            return
        if not question:
            continue
        print(agent.run(question))


if __name__ == "__main__":
    main()
```

Two things worth understanding here:

1. **`sys.path.insert`** adds the parent directory to `sys.path` so that `nl2sql_agent.bindings:list_tables` resolves when you run the script directly (without packaging `nl2sql_agent` as an installable module). For a real project you'd put this in a `pyproject.toml` and `pip install -e .` instead.
2. **`os.environ.setdefault("NL2SQL_DB_PATH", ...)`** makes the script self-contained — it points the bindings at `mock.sqlite` next to the folder unless you've already set the env var.

## Run it

```bash
dotenv run uv run nl2sql_agent/start.py "How many small enterprises are in 海淀区?"
```

You should see something like:

```
There are 2 small enterprises (小型) registered in 海淀区:
  - 测试企业_3
  - 测试企业_17

```sql
SELECT enterprise_name
FROM   enterprise_basic
WHERE  register_district = '海淀区'
  AND  enterprise_scale  = '小型';
```
```

Try a few more:

```bash
dotenv run uv run nl2sql_agent/start.py "Top 5 enterprises by recent valuation"
dotenv run uv run nl2sql_agent/start.py "How many enterprises in each 专精特新 level?"
dotenv run uv run nl2sql_agent/start.py "Show the structure of the AI industry chain"
```

## What you've built

A complete agent in roughly 200 lines of YAML and Python:

```
nl2sql_agent/
├── agent.yaml              ✅ wires everything together
├── system_prompt.md        ✅ workflow and constraints
├── start.py                ✅ Python entry point
├── bindings.py             ✅ list_tables / describe_table / sql_query
├── tools/
│   ├── list_tables.tool.yaml         ✅
│   ├── describe_table.tool.yaml      ✅
│   └── sql_query.tool.yaml           ✅
└── skills/
    ├── enterprise_basic/SKILL.md     ✅
    ├── enterprise_contact/SKILL.md   ✅
    ├── enterprise_financing/SKILL.md ✅
    ├── enterprise_product/SKILL.md   ✅
    ├── industry/SKILL.md             ✅
    ├── industry_enterprise/SKILL.md  ✅
    └── users/SKILL.md                ✅
```

Everything except the `nexau` package itself was code you wrote. The harness took care of the loop, the schema translation, and the skill loading.

## Iterating from here

The most productive feedback loop with an NL2SQL agent looks like this:

1. Ask a question.
2. If the answer is wrong, look at why — usually it picked the wrong table or used the wrong column.
3. Update the **skill** for that table to prevent the mistake next time. Add to "Common values", "Gotchas", or "Example queries".
4. Re-run.

Skills are the agent's long-term memory. The system prompt and tools rarely need to change once they're working; the skills get richer over time as you discover edge cases.

## Next: run it on a different provider

The same `agent.yaml` you just wrote runs on OpenAI Chat Completions, OpenAI Responses (`o1`/`o3`/`gpt-5`), Anthropic Claude, and Google Gemini — by changing the `llm_config` block alone. Tools and skills are translated to the right wire format automatically.

→ [LLM API types](../llm-api-types.md)
