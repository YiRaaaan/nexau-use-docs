# NexAU Docs Tutorial

> 🇨🇳 [中文导读](./zh/README.md)

This repo is a docs-first tutorial for building a real NexAU agent from scratch.
The runnable example lives in [`enterprise_data_agent/`](./enterprise_data_agent/),
and the published docs site is built from the Markdown content in [`zh/`](./zh/).

## What This Repo Contains

- A complete `enterprise_data_agent` example that answers natural-language questions over a 7-table SQLite database of Chinese enterprises
- A chapter-based tutorial that walks from local development to cloud deployment and automation
- Supporting scripts for generating mock data, inspecting schema, and producing SKILL files
- A **[Database Agent Cookbook](./database_agent_cookbook/database_agent_cookbook.ipynb)** — reusable templates, tools, and a Skills auto-generator for building SQL database agents from any SQLite file

## Recommended Reading Path

- Chinese docs entry: [zh/README.md](./zh/README.md)
- First hands-on chapter: [zh/01-bash-nl2sql.md](./zh/01-bash-nl2sql.md)
- Runnable agent files: [enterprise_data_agent/](./enterprise_data_agent/)

## Site Build

This repo uses a lightweight Docsify site. Build the static output with:

```bash
bash build.sh
```

The generated site is written to `dist/`.
