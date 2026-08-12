"""
Pure validation helpers used by tools that touch the OS.

Kept free of pyautogui / docx / reportlab so they can be unit-tested
without the full Windows stack.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

APP_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._\-]{0,63}$")

_BLOCKED_FILENAMES = {
    ".env",
    ".env.local",
    ".gitconfig",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
}

_BLOCKED_DIR_NAMES = {".git", ".ssh"}

# Compared case-insensitively after normalizing slashes.
_BLOCKED_PREFIXES = (
    "c:/windows",
    "c:/program files",
    "c:/program files (x86)",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/boot",
    "/sys",
    "/proc",
)


def is_safe_app_name(name: str) -> bool:
    """Reject empty names and anything that could be shell metacharacters."""
    return bool(APP_NAME_RE.fullmatch((name or "").strip()))


def sanitize_desktop_filename(filename: str, ext: str) -> str:
    """
    Strip any directory component so '../../Windows/evil' cannot escape
    the desktop folder. Ensures the expected extension.
    """
    name = Path(filename or "").name.strip()
    if not name or name in {".", ".."}:
        raise ValueError("Invalid filename.")
    if ext and not name.lower().endswith(ext.lower()):
        name += ext
    return name


def desktop_destination(desktop: str | Path, filename: str, ext: str) -> Path:
    name = sanitize_desktop_filename(filename, ext)
    dest = (Path(desktop) / name).resolve()
    root = Path(desktop).resolve()
    if dest != root and root not in dest.parents:
        raise ValueError("Refused to write outside the desktop folder.")
    return dest


def _norm(path: Path) -> str:
    return str(path).replace("\\", "/").lower()


def _looks_protected(p: Path) -> str | None:
    if p.name.lower() in _BLOCKED_FILENAMES:
        return f"Refused to modify '{p.name}'."
    if any(part.lower() in _BLOCKED_DIR_NAMES for part in p.parts):
        return "Refused to modify files inside a protected directory (.git / .ssh)."
    text = _norm(p)
    for prefix in _BLOCKED_PREFIXES:
        if text == prefix or text.startswith(prefix + "/"):
            return f"Refused to write under a protected system path ({prefix})."
    return None


def reject_write(path: Path, extra_blocked: list[Path] | None = None) -> str | None:
    """
    Return an error message if this path must not be written, else None.
    Blocks secrets files, VCS/SSH dirs, and OS system trees.
    """
    raw = Path(path).expanduser()
    try:
        resolved = raw.resolve()
    except Exception:
        resolved = raw

    for candidate in (raw, resolved):
        msg = _looks_protected(candidate)
        if msg:
            return msg

    if extra_blocked:
        for blocked in extra_blocked:
            try:
                blocked_res = Path(blocked).expanduser().resolve()
            except Exception:
                blocked_res = Path(blocked)
            if resolved == blocked_res or raw == Path(blocked):
                return f"Refused to modify a protected file ({Path(blocked).name})."
    return None


_NON_WEB_SCHEMES = {
    "javascript", "data", "file", "mailto", "about", "vbscript",
    "blob", "ws", "wss", "ftp", "ms-settings", "shell",
}


def coerce_http_url(url: str) -> str | None:
    """
    Return a http(s) URL, prepending https:// when the user omitted a scheme.
    Rejects javascript:, file:, and other non-web schemes.
    """
    raw = (url or "").strip()
    if not raw:
        return None
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", raw)
    if scheme_match:
        scheme = scheme_match.group(1).lower()
        if scheme in _NON_WEB_SCHEMES:
            return None
        if scheme not in ("http", "https") and "://" in raw[:24]:
            return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return raw
