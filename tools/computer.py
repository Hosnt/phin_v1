"""
Computer control tools — the "hands" (and now eyes) of Phin.
Each function is deliberately narrow and named so the LLM's tool-use is predictable.
"""
import base64
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pyautogui
import mss
import mss.tools

from core.config import Config
from core.safety import is_safe_app_name

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Common Windows app aliases -> executable/start command.
APP_ALIASES = {
    "chrome": "chrome",
    "notepad": "notepad",
    "explorer": "explorer",
    "file explorer": "explorer",
    "calculator": "calc",
    "spotify": "spotify",
    "vscode": "code",
    "vs code": "code",
    "word": "winword",
    "excel": "excel",
    "task manager": "taskmgr",
    "settings": "start ms-settings:",
    "terminal": "wt",
}


def open_app(app_name: str) -> str:
    """Open an application by name (Windows).

    Never interpolates the name into a shell string — a previous version
    used `Popen(f"start {cmd}", shell=True)`, which meant a tool call like
    `notepad & calc` (or worse) would run arbitrary commands.
    """
    raw = (app_name or "").strip()
    if not raw:
        return "No app name given."
    if not is_safe_app_name(raw):
        return (
            "Refused to open that app name — it contains characters that "
            "aren't allowed (letters, numbers, spaces, dots, dashes only)."
        )
    key = raw.lower()
    try:
        if key == "settings":
            if sys.platform != "win32":
                return "Settings is only available on Windows."
            subprocess.Popen(["cmd", "/c", "start", "", "ms-settings:"], shell=False)
            return f"Opened {raw}."

        cmd = APP_ALIASES.get(key, raw)
        if sys.platform == "win32":
            # `start` is a cmd builtin. The empty title argument stops a
            # quoted path being treated as the window title.
            subprocess.Popen(["cmd", "/c", "start", "", cmd], shell=False)
        else:
            exe = shutil.which(cmd)
            if not exe:
                return f"Don't know how to open {raw} on this OS."
            subprocess.Popen([exe], shell=False)
        return f"Opened {raw}."
    except Exception as e:
        return f"Failed to open {raw}: {e}"


def take_screenshot(label: str = "screenshot") -> str:
    """Capture the full screen and save it. Returns the saved file path."""
    ts = int(time.time())
    safe_label = "".join(c for c in label if c.isalnum() or c in ("-", "_")) or "screenshot"
    out_path = SCREENSHOT_DIR / f"{safe_label}_{ts}.png"
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=str(out_path))
        return str(out_path)
    except Exception as e:
        return f"Failed to take screenshot: {e}"


def describe_screen(question: str = "What's on the screen right now?") -> str:
    """
    Take a screenshot and actually SEE what's in it by sending it to a
    vision-capable model, then return a text description/answer. Use this
    whenever the user asks what's currently visible, what an app or window
    shows, or to read/describe on-screen content — take_screenshot alone
    only saves a file and cannot answer those questions.
    """
    if not Config.GEMINI_API_KEY:
        return (
            "Can't describe the screen: GEMINI_API_KEY is not set in .env "
            "(vision requires a Gemini key even if the main LLM_PROVIDER is something else)."
        )
    shot_path = take_screenshot("describe")
    if shot_path.startswith("Failed"):
        return shot_path
    try:
        import openai
        with open(shot_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        client = openai.OpenAI(
            api_key=Config.GEMINI_API_KEY,
            base_url=Config.GEMINI_BASE_URL,
        )
        resp = client.chat.completions.create(
            model=Config.GEMINI_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
        )
        return resp.choices[0].message.content or "Couldn't get a description back."
    except Exception as e:
        return f"Failed to analyze screenshot: {e}"


def move_and_click(x: int, y: int, button: str = "left") -> str:
    """Move mouse to (x, y) and click. Use sparingly and only with explicit coordinates."""
    try:
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click(button=button)
        return f"Clicked at ({x}, {y}) with {button} button."
    except Exception as e:
        return f"Failed to click: {e}"


def type_text(text: str) -> str:
    """Type text at the current cursor/focus location."""
    try:
        pyautogui.write(text, interval=0.02)
        return "Text typed."
    except Exception as e:
        return f"Failed to type text: {e}"


def press_hotkey(*keys: str) -> str:
    """Press a keyboard shortcut, e.g. press_hotkey('ctrl', 's')."""
    if not keys:
        return "No keys given."
    try:
        pyautogui.hotkey(*keys)
        return f"Pressed {'+'.join(keys)}."
    except Exception as e:
        return f"Failed to press {'+'.join(keys)}: {e}"


def close_active_window() -> str:
    """Close the currently focused window (Alt+F4)."""
    try:
        pyautogui.hotkey("alt", "f4")
        return "Closed active window."
    except Exception as e:
        return f"Failed to close active window: {e}"
