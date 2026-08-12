"""
Browser control — voice-only tab management.

Uses OS-level keyboard shortcuts (works in whatever browser has focus) plus
`webbrowser` for opening URLs in new tabs. No mouse clicks required.

Note: these hotkeys assume a Chromium/Firefox-style browser (Chrome, Edge,
Firefox) is the focused/active window. If no browser window exists yet,
open_url() launches the OS default browser first.
"""
import time
import webbrowser
from urllib.parse import quote
import pyautogui

from core.safety import coerce_http_url


def open_url(url: str) -> str:
    """Open a URL in a new tab (launches the default browser if none is open)."""
    safe = coerce_http_url(url)
    if not safe:
        return "Refused to open that URL — only http(s) links are allowed."
    webbrowser.open_new_tab(safe)
    return f"Opened {safe} in a new tab."


def search_web(query: str) -> str:
    """Open a new tab and search the web for a query using the default search engine."""
    url = f"https://www.google.com/search?q={quote(query)}"
    webbrowser.open_new_tab(url)
    return f"Searched the web for: {query}"


def new_tab() -> str:
    """Open a new blank tab in the currently focused browser window."""
    pyautogui.hotkey("ctrl", "t")
    return "Opened a new tab."


def close_tab() -> str:
    """Close the currently active tab in the focused browser window."""
    pyautogui.hotkey("ctrl", "w")
    return "Closed the active tab."


def next_tab() -> str:
    """Switch to the next tab in the focused browser window."""
    pyautogui.hotkey("ctrl", "tab")
    return "Switched to the next tab."


def previous_tab() -> str:
    """Switch to the previous tab in the focused browser window."""
    pyautogui.hotkey("ctrl", "shift", "tab")
    return "Switched to the previous tab."


def reopen_closed_tab() -> str:
    """Reopen the most recently closed tab."""
    pyautogui.hotkey("ctrl", "shift", "t")
    return "Reopened the last closed tab."


def go_to_tab_number(n: int) -> str:
    """Jump directly to tab number n (1-8) in the focused browser window."""
    n = max(1, min(int(n), 8))
    pyautogui.hotkey("ctrl", str(n))
    return f"Switched to tab {n}."


def focus_address_bar_and_go(url: str) -> str:
    """Type a URL into the address bar of the currently focused tab and navigate there
    (use this instead of open_url when the user wants to reuse the CURRENT tab, not a new one)."""
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.15)
    if not url.startswith(("http://", "https://")) and "." in url:
        url = "https://" + url
    pyautogui.typewrite(url, interval=0.01)
    pyautogui.press("enter")
    return f"Navigated current tab to {url}."
