"""Entry point for the enterprise data agent.

Usage:
    # one-shot
    uv run enterprise_data_agent/start.py "How many small enterprises are in 海淀区?"

    # interactive
    uv run enterprise_data_agent/start.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent

# Load .env from project root before importing nexau / building the agent,
# so OPENAI_API_KEY and friends are available by the time the agent runs.
load_dotenv(HERE.parent / ".env")

# Make sure tool bindings (`enterprise_data_agent.bindings:...`) resolve when running
# the script directly without installing this directory as a package.
sys.path.insert(0, str(HERE.parent))

# Default the SQLite path to enterprise.sqlite next to this folder.
os.environ.setdefault("ENTERPRISE_DB_PATH", str(HERE.parent / "enterprise.sqlite"))

from nexau import Agent, AgentConfig  # noqa: E402


def main() -> None:
    config = AgentConfig.from_yaml(HERE / "agent.yaml")
    agent = Agent(config=config)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(agent.run(question))
        return

    print("enterprise data agent ready. Type a question (Ctrl-D to exit).")
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
