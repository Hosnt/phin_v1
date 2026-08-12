"""
Lets Phin open/close its own main UI (the dashboard) on command — "open
your dashboard", "show yourself", "pull up your interface", etc.

Only does anything when running with `--native` or `--ui` (there has to be
a HUD server + overlay window listening). In plain `voice`/`text` mode with
no UI at all, these are harmless no-ops.
"""
from ui import server as ui_server


def open_dashboard() -> str:
    ui_server.push_dashboard(True)
    return "Dashboard opened."


def close_dashboard() -> str:
    ui_server.push_dashboard(False)
    return "Dashboard closed."
