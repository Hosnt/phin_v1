"""
Auto-starts `freellmpool proxy` in the background if nothing is already
listening on its port, so Phin never requires a second manually-run window.

Used from every entry point (main.py's text/voice modes, tray.py's silent
pythonw launch via Windows Startup) so this only has to be correct once.
"""
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from core.config import Config

PROXY_LOG_FILE = Config.DATA_DIR / "freellmpool_proxy.log"


def ensure_running_for_config():
    """Only starts the proxy if .env is actually configured to use a local
    OpenAI-compatible endpoint (e.g. freellmpool) — a no-op if LLM_PROVIDER
    is "anthropic" or OPENAI_BASE_URL points somewhere non-local."""
    if Config.LLM_PROVIDER != "openai" or not Config.OPENAI_BASE_URL:
        return
    parsed = urlparse(Config.OPENAI_BASE_URL)
    if parsed.hostname not in ("127.0.0.1", "localhost"):
        return
    ensure_running(host=parsed.hostname, port=parsed.port or 8080)


def ensure_running(host: str = "127.0.0.1", port: int = 8080):
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return  # already running — nothing to do
    except OSError:
        pass

    freellmpool_path = shutil.which("freellmpool")
    if not freellmpool_path:
        print(
            "  [warn] freellmpool is not installed or not on PATH — "
            "LLM calls will fail until you run: pip install freellmpool"
        )
        return

    print(f"Starting freellmpool proxy in the background on :{port} ...")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # IMPORTANT: don't swallow the proxy's own stdout/stderr — if it fails
    # to start (bad config, port conflict, crash), silently discarding that
    # output would leave zero clue why. Redirect to a log file instead so a
    # startup failure is always inspectable.
    log_handle = open(PROXY_LOG_FILE, "w", encoding="utf-8")
    process = subprocess.Popen(
        [freellmpool_path, "proxy"],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    time.sleep(3)  # give it a moment to bind the port before Phin's first request

    # Verify it's actually listening now — a crashed/failed proxy process
    # would otherwise fail silently until the first real LLM call errors out.
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return
    except OSError:
        pass

    exit_code = process.poll()
    print(
        f"  [warn] freellmpool proxy doesn't appear to be listening on :{port} yet "
        f"(process {'exited with code ' + str(exit_code) if exit_code is not None else 'still running'}). "
        f"Check {PROXY_LOG_FILE} for its actual startup output, or run "
        f"`freellmpool proxy` by hand in a separate terminal to see errors live."
    )

