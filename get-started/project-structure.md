# Project structure

Before we write any code, let's lay out the folder. NexAU doesn't enforce a directory shape, but every project that uses YAML-defined agents follows the same shape, and sticking to it makes your agent portable.

This page shows the **target layout** for the NL2SQL agent we're going to build. Every subsequent tutorial page will fill in one of these files.

## What we're going to create

```
nl2sql_agent/
├── agent.yaml              # ← the main config that wires everything together
├── system_prompt.md        # ← the agent's instructions (rendered as Jinja2)
├── start.py                # ← Python entry point
├── bindings.py             # ← Python implementations for the SQL tools
│
├── tools/                  # ← schemas the model sees, one *.tool.yaml per tool
│   ├── list_tables.tool.yaml
│   ├── describe_table.tool.yaml
│   └── sql_query.tool.yaml
│
└── skills/                 # ← Claude-Skill-compatible knowledge folders, one per DB table
    ├── enterprise_basic/
    │   └── SKILL.md
    ├── enterprise_contact/
    │   └── SKILL.md
    ├── enterprise_financing/
    │   └── SKILL.md
    ├── enterprise_product/
    │   └── SKILL.md
    ├── industry/
    │   └── SKILL.md
    ├── industry_enterprise/
    │   └── SKILL.md
    └── users/
        └── SKILL.md
```

The `mock.sqlite` file lives one level up — that's the database the agent reads.

## Why this layout

There are three kinds of file at play. Each one is the source of truth for a different concern.

### 1. `agent.yaml` — the wiring

`agent.yaml` is the only file that knows about every other file. It points at the system prompt, lists the tools and skills, and configures the LLM. Most edits during development happen here.

### 2. `tools/*.tool.yaml` + `bindings.py` — what the agent can do

NexAU **decouples a tool's schema from its implementation**. The schema (what the model sees: name, description, parameters) lives in a `*.tool.yaml`. The Python implementation lives in `bindings.py`. They're glued together at load time by the `binding:` field in `agent.yaml`:

```yaml
tools:
  - name: sql_query
    yaml_path: ./tools/sql_query.tool.yaml
    binding: nl2sql_agent.bindings:sql_query
```

The `binding` value uses `module.path:callable` syntax — same as setuptools entry points. NexAU imports the module and grabs the attribute when the agent loads.

Why split them? Because the schema is *prompt engineering* — wording matters, descriptions are read by the model — while the implementation is *code*. They evolve at different rates and you want to edit the prompt without touching code.

### 3. `skills/<table>/SKILL.md` — the agent's domain knowledge

For an NL2SQL agent, raw column names aren't enough. The model needs to know:

- What each table is *for*
- When to use it vs. another table
- The business meaning of each column
- Common values (enums, formats)
- Example queries
- Gotchas (e.g. `register_capital` is stored as TEXT and needs `CAST(... AS REAL)`)

You could cram all this into the system prompt, but it gets unwieldy fast. NexAU's **Skills** are a better answer: each skill is a folder with a `SKILL.md`, and the skill is loaded into the agent's context at startup. We give the agent **one skill per database table**, mirroring the design from the [database SKILL design doc](../260407 数据库 SKILL 整理.pdf).

The format is the same as Anthropic's Claude Skills, so you can drop in skills written for Claude and they'll work as-is.

## How NexAU resolves paths

Inside a YAML file, all relative paths (`yaml_path`, `system_prompt`, `binding` modules, skill folders) are resolved **relative to the YAML file itself**. This is why moving `nl2sql_agent/` around works without rewriting paths.

Environment variables can be referenced anywhere with `${env.VAR_NAME}`:

```yaml
llm_config:
  model: ${env.LLM_MODEL}
  base_url: ${env.LLM_BASE_URL}
  api_key: ${env.LLM_API_KEY}
```

This is why `agent.yaml` works across dev/staging/prod without edits — only `.env` changes.

## Where things load from

| YAML field | Resolved as |
|---|---|
| `system_prompt: ./system_prompt.md` | File path, relative to the YAML |
| `tools[].yaml_path` | Path to a `*.tool.yaml` file |
| `tools[].binding` | Python import string `module.path:callable` |
| `skills[]` | Folder containing a `SKILL.md` |
| `middlewares[].import` / `tracers[].import` | Python import string `module.path:Class` |
| `${env.VAR_NAME}` | Looked up at agent-load time from environment |

## Create the folder

```bash
mkdir -p nl2sql_agent/tools nl2sql_agent/skills
cd nl2sql_agent
```

That's the scaffolding. Next we'll fill in the most important file: the SQL tools the agent uses to talk to the database.

→ [Writing the SQL tools](./tool-yaml.md)
