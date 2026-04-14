# Database Agent Cookbook

> From any SQLite database to a natural-language-queryable NexAU Agent in 5 minutes.

For a detailed walkthrough of **why** each component is designed the way it is, see the [Jupyter Notebook](./database_agent_cookbook.ipynb).

## Components

| Component | Description |
|---|---|
| `execute_sql` tool | Three-layer secure, read-only SQL executor for any SQLite |
| SKILL.md template | Per-table domain knowledge in a best-practice format |
| `generate_skills.py` | Auto-generates SKILL.md files from any SQLite database |
| System prompt template | 7-step workflow prompt for database agents |
| `agent.yaml` + `start.py` | Ready-to-use agent configuration |

## Directory structure

```
database_agent_cookbook/
├── README.md                           <- you are here
├── database_agent_cookbook.ipynb        <- detailed tutorial notebook
├── create_sample_db.py                 # Generate sample bookstore database
├── generate_skills.py                  # Auto-generate Skills from any SQLite
├── sample.sqlite                       # Sample DB (created by create_sample_db.py)
│
├── template/                           # Copy-and-use agent template
│   ├── agent.yaml
│   ├── nexau.json
│   ├── system_prompt.md
│   ├── start.py
│   └── tools/
│       ├── execute_sql.py              # SQL tool implementation
│       ├── ExecuteSQL.tool.yaml        # SQL tool schema
│       └── TodoWrite.tool.yaml         # Planning tool schema
│
├── skills_template/
│   └── SKILL.md.template              # SKILL.md writing template
│
└── examples/
    └── skills/                         # Polished Skills for the sample database
        ├── customers/SKILL.md
        ├── books/SKILL.md
        └── orders/SKILL.md
```

## Quick start

```bash
# 1. Copy the template
cp -r database_agent_cookbook/template/ my_db_agent/

# 2. Prepare your database (or use the sample)
python database_agent_cookbook/create_sample_db.py

# 3. Auto-generate Skills
python database_agent_cookbook/generate_skills.py your_database.sqlite -o my_db_agent/skills

# 4. Register Skills in agent.yaml
# Uncomment the skills: section and add your table paths

# 5. Configure environment variables
cat >> .env << 'EOF'
DB_PATH=./your_database.sqlite
LLM_MODEL=your-model-name
LLM_BASE_URL=https://your-llm-api.com/v1
LLM_API_KEY=sk-xxx
EOF

# 6. Run
uv run my_db_agent/start.py "Which book is the most expensive?"
```

## Adapting for other databases

| File | What to change |
|---|---|
| `execute_sql.py` | Replace `sqlite3` with target driver (`psycopg2`, `pymysql`) |
| `ExecuteSQL.tool.yaml` | Update SQL dialect notes in `description` |
| `system_prompt.md` | Update "Engine: SQLite" to target database |
| `generate_skills.py` | Replace `PRAGMA table_info` with `information_schema` queries |

## Relationship to the tutorial

This Cookbook distills and generalizes Chapters 2-4 of the [main tutorial](../zh/README.md):

| Tutorial | Cookbook |
|---|---|
| Ch 2: Write `execute_sql` for a specific DB | Generic `execute_sql` for any SQLite |
| Ch 3: Hand-write 7 table Skills | SKILL.md template + `generate_skills.py` |
| Ch 4: Mount `write_todos` | Included in template, ready to use |

The tutorial is for **learning principles**; the Cookbook is for **quick reuse**.
