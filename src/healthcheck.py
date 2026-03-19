"""Lightweight health-check server and CLI probe.

A tiny HTTP server runs inside the bot process on a configurable port
(default 8080).  Docker (or any orchestrator) can hit ``GET /health``
to confirm the process is alive and the last monitoring cycle completed
recently.

The module also works as a standalone CLI script so it can be used as
``HEALTHCHECK CMD python -m src.healthcheck`` inside a Dockerfile.
"""

import asyncio
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional

from loguru import logger

# ── Shared state (written by the scheduler, read by the HTTP handler) ──

_state: dict = {
    "status": "starting",
    "started_at": time.time(),
    "last_cycle": 0.0,
    "cycles": 0,
    "pid": os.getpid(),
}

HEALTHCHECK_PORT = int(os.getenv("HEALTHCHECK_PORT", "8080"))
# Max seconds since last successful cycle before we report unhealthy
MAX_CYCLE_AGE = int(os.getenv("HEALTHCHECK_MAX_CYCLE_AGE", "300"))


def update_health(*, status: str = "running", cycles: int = 0) -> None:
    """Called by the scheduler after every successful cycle."""
    _state["status"] = status
    _state["last_cycle"] = time.time()
    _state["cycles"] = cycles


def mark_ready() -> None:
    """Called once after initial setup completes."""
    _state["status"] = "running"


def mark_stopping() -> None:
    """Called during graceful shutdown."""
    _state["status"] = "stopping"


# ── HTTP handler ────────────────────────────────────────────────────

class _HealthHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler — responds only to ``GET /health``."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(404)
            return

        now = time.time()
        uptime = int(now - _state["started_at"])
        cycle_age = int(now - _state["last_cycle"]) if _state["last_cycle"] else None

        healthy = (
            _state["status"] in ("running", "starting")
            and (cycle_age is None or cycle_age < MAX_CYCLE_AGE)
        )

        body = {
            "status": "healthy" if healthy else "unhealthy",
            "bot_status": _state["status"],
            "uptime_seconds": uptime,
            "last_cycle_seconds_ago": cycle_age,
            "cycles_completed": _state["cycles"],
            "pid": _state["pid"],
        }

        code = 200 if healthy else 503
        payload = json.dumps(body).encode()

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # Silence the default stderr log line for every request
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


# ── Background server (started inside the bot process) ──────────────

_server: Optional[HTTPServer] = None


def start_health_server(port: int = HEALTHCHECK_PORT) -> None:
    """Start the health-check HTTP server on a daemon thread."""
    global _server  # noqa: PLW0603

    try:
        _server = HTTPServer(("0.0.0.0", port), _HealthHandler)
        thread = Thread(target=_server.serve_forever, daemon=True)
        thread.start()
        logger.info("Health-check server listening on :{port}", port=port)
    except OSError as exc:
        logger.warning("Could not start health-check server: {err}", err=exc)


def stop_health_server() -> None:
    """Gracefully stop the health-check server."""
    if _server is not None:
        _server.shutdown()


# ── CLI probe (used by Dockerfile HEALTHCHECK) ──────────────────────

def _probe(port: int = HEALTHCHECK_PORT) -> int:
    """Hit the local health endpoint; return 0 on success, 1 on failure."""
    import urllib.request
    import urllib.error

    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return 0 if resp.status == 200 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(_probe())
