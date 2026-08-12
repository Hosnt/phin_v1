"""
Native desktop overlay for Phin — a real floating OS window (pywebview),
not a browser tab. Loads the exact same ui/overlay.html + Flask/socket.io
HUD as before, just rendered inside a frameless, transparent, always-on-top
window instead of Chrome/Brave.

Two sizes:
  - ORB: a small circle docked near the screen edge. This is the resting
    state, and what auto-expand/auto-collapse animate to/from as Phin
    starts/stops doing things.
  - DASHBOARD: a bigger centered panel with the full console — status,
    transcript history, system stats. Opened on command ("open the
    dashboard" / "show yourself") via the open_dashboard tool, and stays
    open (doesn't auto-collapse) until closed the same way or pinned shut.

Run with:  python main.py voice --native
This must run on the main thread (pywebview requirement on Windows), so
main.py starts the voice loop in a background thread and calls
native_overlay.launch() last, from __main__.
"""
import threading
import time

import webview

ORB_W = 100           # a little wider than the 74px orb graphic itself so
                      # the status label text underneath it isn't clipped
ORB_H = 112           # orb circle + the "STANDING BY" / "HEARING YOU" label
CONSOLE_W = 340       # auto-expand size while Phin is doing something
CONSOLE_H = 480
DASHBOARD_W = 420     # bigger, centered, manually-opened main UI
DASHBOARD_H = 640
EDGE_MARGIN = 24


def _screen_size():
    try:
        screens = webview.screens
        if screens:
            return screens[0].width, screens[0].height
    except Exception:
        pass
    return 1920, 1080


class OverlayAPI:
    """Exposed to the page as `pywebview.api.*`. The window is frameless, so
    every resize/move/close has to be driven from here rather than by the OS
    chrome the window doesn't have."""

    def __init__(self):
        self.window = None  # set right after create_window()
        self.collapsed = True
        self.pinned = False  # True while the dashboard is manually open —
                              # blocks the idle auto-collapse timer.
        screen_w, screen_h = _screen_size()
        self.orb_pos = (screen_w - ORB_W - EDGE_MARGIN, screen_h // 2 - ORB_H // 2)
        self._screen_w = screen_w
        self._screen_h = screen_h

    def expand(self):
        """Auto-expand to the small console, anchored near the orb."""
        if not self.window or self.pinned or not self.collapsed:
            return
        self.collapsed = False
        ox, oy = self.orb_pos
        x = ox + ORB_W - CONSOLE_W
        y = max(EDGE_MARGIN, min(oy - CONSOLE_H // 2 + ORB_H // 2,
                                  self._screen_h - CONSOLE_H - EDGE_MARGIN))
        self.window.resize(CONSOLE_W, CONSOLE_H)
        self.window.move(max(EDGE_MARGIN, x), y)

    def collapse(self):
        if not self.window or self.pinned or self.collapsed:
            return
        self.collapsed = True
        ox, oy = self.orb_pos
        self.window.resize(ORB_W, ORB_H)
        self.window.move(ox, oy)

    def open_dashboard(self):
        """Manually-triggered main UI — bigger, centered, stays open."""
        if not self.window:
            return
        self.pinned = True
        self.collapsed = False
        x = (self._screen_w - DASHBOARD_W) // 2
        y = (self._screen_h - DASHBOARD_H) // 2
        self.window.resize(DASHBOARD_W, DASHBOARD_H)
        self.window.move(max(0, x), max(0, y))

    def close_dashboard(self):
        if not self.window:
            return
        self.pinned = False
        self.collapse()

    def quit(self):
        if self.window:
            self.window.destroy()


def _track_orb_position(api: OverlayAPI):
    """While collapsed, remember where the user dragged the orb to, so the
    next expand() re-anchors near it instead of snapping back."""
    while True:
        try:
            if api.window and api.collapsed:
                x, y = api.window.x, api.window.y
                if x is not None and y is not None:
                    api.orb_pos = (x, y)
        except Exception:
            pass
        time.sleep(0.5)


def launch(url: str = "http://localhost:5151", start_collapsed: bool = True):
    """Blocks until the overlay is closed. Call this LAST, on the main
    thread — start the HUD server and voice/text loop in background threads
    first."""
    api = OverlayAPI()
    pos = api.orb_pos
    api.collapsed = start_collapsed

    window = webview.create_window(
        "Phin",
        url,
        width=ORB_W, height=ORB_H,
        x=max(EDGE_MARGIN, pos[0]), y=pos[1],
        frameless=True,
        easy_drag=True,     # click-and-drag anywhere moves the window (no titlebar)
        on_top=True,
        transparent=True,   # gives the orb a true circular shape instead of
                             # a square box — safe on the pinned pywebview
                             # version (see requirements.txt note); the 6.x
                             # crash this used to trigger is a regression in
                             # that specific newer release, not in 4.4.1.
        resizable=False,
        js_api=api,
    )
    api.window = window

    threading.Thread(target=_track_orb_position, args=(api,), daemon=True).start()

    webview.start()
