"""Inbox Bridge — entry point.

Designed to run as a long-lived daemon inside Docker or systemd.
Handles SIGTERM / SIGINT for graceful shutdown.
"""

import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)


def _run() -> None:
    from src.main import main

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Graceful Ctrl+C — scheduler already handles cleanup


if __name__ == "__main__":
    _run()
