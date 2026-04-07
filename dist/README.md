# NexAU — Build an Agent from 0 to 1

> 🇨🇳 [中文版](./zh/README.md)

NexAU is a general-purpose agent framework for building tool-using LLM agents. You define an agent — its model, prompt, tools, sub-agents, skills, and middleware — in a single YAML file, and run it from the command line or from Python.

These docs are a hands-on tutorial. By the end, you will have built a real **NL2SQL agent** that answers natural-language questions about a SQLite database of Chinese enterprises. We use that one running example throughout, so every code snippet you read is part of an agent you can actually run.

## What we're building

A read-only NL2SQL agent over a 7-table enterprise database. Ask it questions in plain language; it picks the right table(s), writes SQLite, runs the query, and returns a grounded answer with the SQL it used.

```
> Top 5 enterprises by registered capital in 海淀区?

The five enterprises in 海淀区 with the highest registered capital are:
  1. 测试企业_12  — 49,371.25 万元 (小型, 制造业)
  2. 测试企业_07  — 38,210.00 万元 (中型, 信息传输...)
  ...

```sql
SELECT enterprise_name, register_capital, enterprise_scale, industry_level1
FROM   enterprise_basic
WHERE  register_district = '海淀区'
ORDER  BY CAST(register_capital AS REAL) DESC
LIMIT  5;
```
```

The full agent we build lives in [`nl2sql_agent/`](./nl2sql_agent/) at the repo root. You can run it the moment you finish the Quickstart.

## How NexAU thinks about agents

We think of NexAU as a **YAML-first agent harness**. Three ideas matter:

1. **Tools are decoupled from their implementation.** A `*.tool.yaml` file holds the schema the model sees; a Python function holds the actual behavior. They're bound together at load time. This is how the same tool can target OpenAI, Anthropic, and Gemini wire formats without rewriting.
2. **Skills are first-class context.** For an NL2SQL agent the schema isn't enough — the model needs to know what each column *means*, when to use a table, and what gotchas to watch for. NexAU loads Claude-Skill-compatible folders so you can author this knowledge once and reuse it.
3. **Provider switching is one block.** The same agent runs across OpenAI Chat Completions, OpenAI Responses, Anthropic, and Gemini — change the `api_type` field and nothing else.

## Tutorial path

Read these in order. Each step ends with something you can run.

| | Step | What you build |
|---|---|---|
| 1 | [Quickstart](./get-started/quickstart.md) | Install NexAU, set env, run the finished example to feel it work |
| 2 | [Project structure](./get-started/project-structure.md) | Lay out an `nl2sql_agent/` folder |
| 3 | [Writing the SQL tools](./get-started/tool-yaml.md) | `list_tables`, `describe_table`, `sql_query` — schemas + Python bindings |
| 4 | [Writing the table Skills](./get-started/skills.md) | One Skill per table — the model's database knowledge base |
| 5 | [Writing the agent YAML](./get-started/agent-yaml.md) | Wire tools, skills, system prompt, LLM, and middlewares together |
| 6 | [Running across providers](./llm-api-types.md) | Swap the same agent across OpenAI, Anthropic, and Gemini |

## Conventions

- Code blocks marked `yaml` are real files you'll create.
- Code blocks marked `python` are the Python tool bindings — short and dependency-light.
- File paths like `nl2sql_agent/tools/sql_query.tool.yaml` always refer to the runnable example in this repo.
- Environment variables use `${env.VAR_NAME}` inside YAML and `os.getenv("VAR_NAME")` in Python.

Ready? Start with the [Quickstart →](./get-started/quickstart.md)
