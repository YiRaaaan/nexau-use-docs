"""Entry point for the database agent.

Usage:
    # one-shot
    uv run start.py "How many rows are in the users table?"

    # interactive
    uv run start.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent

load_dotenv(HERE.parent / ".env")

sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

# Set DB_PATH if not already set — default to sample.sqlite in cookbook root.
os.environ.setdefault("DB_PATH", str(HERE.parent / "sample.sqlite"))

from nexau import Agent, AgentConfig  # noqa: E402


def main() -> None:
    config = AgentConfig.from_yaml(HERE / "agent.yaml")
    agent = Agent(config=config)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(agent.run(message=question))
        return

    print("Database agent ready. Type a question (Ctrl-D to exit).")
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            print()
            return
        if not question:
            continue
        print(agent.run(message=question))


if __name__ == "__main__":
    main()
