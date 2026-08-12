"""
Runs Phin as a background system tray app instead of a console window.

- Voice loop + HUD server run in daemon threads.
- A tray icon (bottom-right of the taskbar) shows Phin is alive and gives
  you Show Dashboard / Pause Listening / Quit without ever touching a
  terminal.
- If the voice loop thread dies for any reason, it's automatically
  restarted (with a short backoff) instead of silently going deaf until
  someone notices and restarts main.py by hand.

Usage:  python tray.py
For true "always running, every login" behavior without opening a terminal
at all, see install_startup.bat, which points a shortcut in the Windows
Startup folder at pythonw.exe running this file (pythonw = no console window).
"""
import sys
import threading
import time

import pystray
from PIL import Image, ImageDraw

from core.config import Config
from core import llm_proxy, runtime
from ui import server as ui_server

_should_run = threading.Event()
_should_run.set()


def _make_icon_image():
    """Small cyan reactor-ring dot, matching the HUD's visual identity, so
    the tray icon doesn't look like a generic default Python icon."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], outline=(72, 224, 255, 255), width=5)
    draw.ellipse([size // 2 - 8, size // 2 - 8, size // 2 + 8, size // 2 + 8],
                 fill=(72, 224, 255, 255))
    return img


def _voice_loop_supervisor():
    """Runs main.run_voice_loop() and restarts it if it ever exits/crashes,
    instead of leaving Phin permanently deaf after one unhandled error."""
    import main as phin_main
    phin_main._hud = phin_main._LiveHud()  # real __init__ path — sets up
                                             # _server AND _last_hearing;
                                             # __init__ also calls
                                             # ui_server.start_in_background(),
                                             # which is a safe no-op since we
                                             # already started it below.

    backoff = 2
    while _should_run.is_set() and not runtime.should_stop():
        try:
            phin_main.run_voice_loop()
            # Returns on a clean "stop"/"exit" voice command, or when
            # runtime.request_stop() is set from the tray Quit item.
            break
        except Exception as e:
            print(f"  [tray] voice loop crashed ({e}); restarting in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)


def _on_show_dashboard(icon, item):
    ui_server.push_dashboard(True)
    ui_server.push_status("idle", "STANDING BY")
    import webbrowser
    webbrowser.open("http://localhost:5151")


def _on_pause(icon, item):
    paused = runtime.toggle_pause()
    if paused:
        icon.title = f"{Config.ASSISTANT_NAME} — paused"
        ui_server.push_status("idle", "PAUSED")
    else:
        icon.title = f"{Config.ASSISTANT_NAME} — listening"
        ui_server.push_status("idle", "STANDING BY")


def _on_quit(icon, item):
    runtime.request_stop()
    _should_run.clear()
    icon.stop()
    sys.exit(0)


def run():
    problems = Config.validate(require_voice=True)
    if problems:
        print("Configuration problems found in .env:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    llm_proxy.ensure_running_for_config()
    ui_server.start_in_background()
    threading.Thread(target=_voice_loop_supervisor, daemon=True).start()

    icon = pystray.Icon(
        "phin",
        _make_icon_image(),
        f"{Config.ASSISTANT_NAME} — listening",
        menu=pystray.Menu(
            pystray.MenuItem("Show Dashboard", _on_show_dashboard, default=True),
            pystray.MenuItem("Pause / Resume Listening", _on_pause),
            pystray.MenuItem("Quit Phin", _on_quit),
        ),
    )
    icon.run()


if __name__ == "__main__":
    run()
