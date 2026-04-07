"""Entry point for the NL2SQL agent.

Usage:
    # one-shot
    dotenv run uv run nl2sql_agent/start.py "How many small enterprises are in 海淀区?"

    # interactive
    dotenv run uv run nl2sql_agent/start.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from nexau import Agent, AgentConfig

HERE = Path(__file__).resolve().parent

# Make sure tool bindings (`nl2sql_agent.bindings:...`) resolve when running
# the script directly without installing this directory as a package.
sys.path.insert(0, str(HERE.parent))

# Default the SQLite path to enterprise.sqlite next to this folder.
os.environ.setdefault("NL2SQL_DB_PATH", str(HERE.parent / "enterprise.sqlite"))


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
