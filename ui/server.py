"""
Serves ui/overlay.html and exposes push_status()/push_transcript() that
main.py calls directly (same process, no network hop) so the HUD reflects
what Phin is actually doing in real time.

Run standalone for design preview only: python ui/server.py
"""
import threading
import time
from pathlib import Path
from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import psutil

app = Flask(__name__, static_folder=None)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

UI_DIR = Path(__file__).resolve().parent
_server_thread = None
_stats_thread = None


@app.route("/")
def index():
    return send_from_directory(UI_DIR, "overlay.html")


def push_status(state: str, text: str = ""):
    """state: 'idle' | 'listening' | 'thinking' | 'tool' | 'speaking'"""
    socketio.emit("status", {"state": state, "text": text})


def push_transcript(text: str, speaker: str = "user"):
    socketio.emit("transcript", {"text": text, "speaker": speaker})


def push_hearing(active: bool):
    """Lets the HUD show a live 'is the mic actually picking anything up'
    indicator while Phin is listening for the wake word or a command, so it
    doesn't look like it's just sitting there doing nothing."""
    socketio.emit("hearing", {"active": bool(active)})


def push_dashboard(open_: bool):
    """Tells the native overlay to snap open into the big centered
    dashboard (open_=True) or back down to the orb (open_=False). Called by
    the open_dashboard/close_dashboard tools — has no effect in plain
    browser-tab mode (--ui) since there's no native window to resize."""
    socketio.emit("dashboard", {"open": open_})


def _push_stats_loop():
    """Emit live CPU/RAM percentages every 2s for the HUD's gauge rings."""
    while True:
        try:
            socketio.emit("stats", {
                "cpu": psutil.cpu_percent(interval=None),
                "ram": psutil.virtual_memory().percent,
            })
        except Exception:
            pass
        time.sleep(2)


def start_in_background(port: int = 5151):
    """Start the HUD server in a daemon thread so main.py's voice loop can
    keep running in the foreground. Safe to call once at startup."""
    global _server_thread, _stats_thread
    if _server_thread is not None:
        return
    def _run():
        socketio.run(app, port=port, debug=False, use_reloader=False,
                      allow_unsafe_werkzeug=True)
    _server_thread = threading.Thread(target=_run, daemon=True)
    _server_thread.start()
    _stats_thread = threading.Thread(target=_push_stats_loop, daemon=True)
    _stats_thread.start()
    print(f"HUD available at http://localhost:{port}")


if __name__ == "__main__":
    # Standalone design-preview mode: demo-cycles state on its own since
    # nothing is pushing real events (see overlay.html's DEMO_MODE flag).
    socketio.run(app, port=5151, debug=True)
