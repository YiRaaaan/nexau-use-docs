# Quickstart

The fastest way to understand NexAU is to run the finished NL2SQL agent **once**, see it answer a real question, and then go back and rebuild it from scratch. This page covers the "run once" part. The rest of the tutorial walks you through every file.

By the end of this page you'll have:

- NexAU installed
- A `.env` configured for your LLM provider
- A working NL2SQL agent answering questions about a 7-table SQLite database

Total time: under 5 minutes.

## 1. Install NexAU

Clone the NexAU repo and install it in editable mode:

```bash
git clone https://github.com/nex-agi/NexAU.git
cd NexAU
uv pip install -e .   # or: pip install -e .
```

You'll also need SQLite — it ships with Python, nothing to install — and a `.env` loader if you don't have one:

```bash
uv pip install python-dotenv
```

## 2. Get the example

The finished NL2SQL agent and its mock database live in this repo:

```
nexau-use-docs/
├── mock.sqlite                  ← 7-table sanitized enterprise database
└── nl2sql_agent/
    ├── agent.yaml
    ├── system_prompt.md
    ├── start.py
    ├── bindings.py              ← Python tool implementations
    ├── tools/                   ← *.tool.yaml schemas
    │   ├── list_tables.tool.yaml
    │   ├── describe_table.tool.yaml
    │   └── sql_query.tool.yaml
    └── skills/                  ← one folder per table
        ├── enterprise_basic/SKILL.md
        ├── enterprise_contact/SKILL.md
        ├── enterprise_financing/SKILL.md
        ├── enterprise_product/SKILL.md
        ├── industry/SKILL.md
        ├── industry_enterprise/SKILL.md
        └── users/SKILL.md
```

If you're reading these docs *inside* this repo, you already have everything. Otherwise clone it.

## 3. Configure environment

Create a `.env` file at the repo root:

```dotenv
LLM_MODEL=gpt-4o
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
```

NexAU's YAML loader expands `${env.VAR}` placeholders, so `agent.yaml` already references these three variables — you don't have to edit YAML when you change providers.

> Want to use Claude or Gemini instead? See [LLM API types](../llm-api-types.md). The `agent.yaml` stays the same; only the `llm_config` block changes.

## 4. Run the agent

Two ways. Pick whichever you prefer.

### From Python

```bash
dotenv run uv run nl2sql_agent/start.py "How many small enterprises are in 海淀区?"
```

You should see something like:

```
There are 2 small enterprises (小型) registered in 海淀区: 测试企业_3 and 测试企业_17.

```sql
SELECT enterprise_name
FROM   enterprise_basic
WHERE  register_district = '海淀区'
  AND  enterprise_scale  = '小型';
```
```

Drop the question argument to enter interactive mode:

```bash
dotenv run uv run nl2sql_agent/start.py
> Top 5 enterprises by recent valuation
> ...
```

### From the NexAU CLI

```bash
./run-agent nl2sql_agent/agent.yaml
```

The CLI gives you the best debugging view: tool calls, sub-agent traces, and multi-round HITL.

## 5. What just happened

When you ran the agent, NexAU:

1. Loaded `nl2sql_agent/agent.yaml`, expanded `${env.*}` placeholders, and constructed an `LLMConfig` for OpenAI Chat Completions
2. Loaded each tool's `*.tool.yaml`, bound it to the Python function in `bindings.py`, and translated the JSON schemas to OpenAI function definitions
3. Loaded each `skills/<table>/SKILL.md` and prepended their content to the agent's context, so the model knows the business meaning of every column
4. Rendered `system_prompt.md` and started a tool-calling loop:
   - The model picked the right table(s) from the SKILLs
   - Called `sql_query` with a SELECT
   - NexAU executed the SQL against `mock.sqlite` (read-only) and returned rows
   - The model wrote the natural-language answer

That's the entire NexAU mental model: **YAML wires together a model, a system prompt, some tools, and some skills, and the harness runs the loop.**

## Next: rebuild it from scratch

Now that you've seen it work, the rest of the tutorial walks you through **building the same agent file by file**:

1. [Project structure](./project-structure.md) — what files we'll create
2. [Writing the SQL tools](./tool-yaml.md) — `list_tables`, `describe_table`, `sql_query`
3. [Writing the table Skills](./skills.md) — one Skill per table
4. [Writing the agent YAML](./agent-yaml.md) — pulling it all together
