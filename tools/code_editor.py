"""
Code and text file editing — lets Phin read a real file on disk, then
overwrite or patch it based on what you asked for, entirely by voice.

Safety note: these tools operate on real files anywhere you point them
(not sandboxed to Desktop like tools/files.py's create_* functions), since
"rewrite my code" implies an existing project path. The LLM is instructed to
confirm before overwriting something it hasn't just read in the same turn.
"""
from pathlib import Path

from core.config import Config
from core.safety import reject_write

MAX_READ_CHARS = 12000  # keep file reads from blowing out the context window


def _resolve(path: str) -> Path:
    return Path(path).expanduser()


def _protected_paths() -> list[Path]:
    return [Config.MEMORY_DB, Config.ROOT_DIR / ".env"]


def _guard_write(path: str) -> tuple[Path, str | None]:
    p = _resolve(path)
    return p, reject_write(p, extra_blocked=_protected_paths())


def read_file(path: str) -> str:
    """Read a text/code file from disk so its contents can be discussed or rewritten."""
    p = _resolve(path)
    if not p.exists():
        return f"File not found: {p}"
    if not p.is_file():
        return f"Not a file: {p}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Failed to read {p}: {e}"
    if len(text) > MAX_READ_CHARS:
        return (
            f"[File is {len(text)} chars, showing first {MAX_READ_CHARS}]\n\n"
            + text[:MAX_READ_CHARS]
        )
    return text


def write_file(path: str, content: str, create_dirs: bool = True) -> str:
    """Overwrite (or create) a file at an exact path with new content.
    Use this for 'rewrite this file' / 'save this code to X' requests."""
    p, blocked = _guard_write(path)
    if blocked:
        return blocked
    try:
        if create_dirs:
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} chars to {p}"
    except Exception as e:
        return f"Failed to write {p}: {e}"


def find_replace_in_file(path: str, find: str, replace: str, count: int = -1) -> str:
    """Find-and-replace a specific snippet inside a file without rewriting the whole thing.
    Prefer this over write_file for small, targeted edits — it's safer and preserves
    everything else in the file exactly as-is."""
    p, blocked = _guard_write(path)
    if blocked:
        return blocked
    if not p.exists():
        return f"File not found: {p}"
    text = p.read_text(encoding="utf-8", errors="replace")
    if find not in text:
        return f"Could not find the given snippet in {p} — nothing changed."
    occurrences = text.count(find)
    new_text = text.replace(find, replace, count if count > 0 else -1)
    p.write_text(new_text, encoding="utf-8")
    replaced = occurrences if count <= 0 else min(count, occurrences)
    return f"Replaced {replaced} occurrence(s) in {p}"


def append_to_file(path: str, content: str) -> str:
    """Append content to the end of an existing file (or create it if missing)."""
    p, blocked = _guard_write(path)
    if blocked:
        return blocked
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} chars to {p}"
    except Exception as e:
        return f"Failed to append to {p}: {e}"


def list_directory(path: str) -> str:
    """List files and folders in a directory, so Phin knows what's there before editing."""
    p = _resolve(path)
    if not p.exists():
        return f"Directory not found: {p}"
    entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    lines = [f"{'📄' if e.is_file() else '📁'} {e.name}" for e in entries[:200]]
    return "\n".join(lines) if lines else "(empty directory)"
