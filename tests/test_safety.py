"""Unit tests for the OS-touching validators — no Windows stack required."""
from pathlib import Path

import pytest

from core.runtime import (
    interrupt_listening,
    is_paused,
    request_stop,
    reset,
    resume,
    should_stop,
    toggle_pause,
)
from core.safety import (
    coerce_http_url,
    desktop_destination,
    is_safe_app_name,
    reject_write,
    sanitize_desktop_filename,
)


def test_safe_app_names():
    assert is_safe_app_name("notepad")
    assert is_safe_app_name("VS Code")
    assert is_safe_app_name("chrome.exe")
    assert not is_safe_app_name("")
    assert not is_safe_app_name("notepad & calc")
    assert not is_safe_app_name("notepad; whoami")
    assert not is_safe_app_name("foo|bar")
    assert not is_safe_app_name("../../Windows/System32/cmd")
    assert not is_safe_app_name("ms-settings:")


def test_desktop_filename_strips_traversal(tmp_path):
    dest = desktop_destination(tmp_path, "../../secret.txt", ".txt")
    assert dest.parent == tmp_path.resolve()
    assert dest.name == "secret.txt"


def test_desktop_filename_adds_extension(tmp_path):
    dest = desktop_destination(tmp_path, "notes", ".txt")
    assert dest.name == "notes.txt"


def test_desktop_rejects_empty_name(tmp_path):
    with pytest.raises(ValueError):
        desktop_destination(tmp_path, "..", ".txt")


def test_reject_write_blocks_env_and_system_paths(tmp_path):
    assert reject_write(tmp_path / ".env")
    assert reject_write(Path(r"C:\Windows\System32\drivers\etc\hosts"))
    assert reject_write(Path("/etc/passwd"))
    assert reject_write(tmp_path / ".git" / "config")
    assert reject_write(tmp_path / ".ssh" / "id_rsa")
    harmless = tmp_path / "project" / "main.py"
    harmless.parent.mkdir()
    assert reject_write(harmless) is None


def test_reject_write_extra_blocked(tmp_path):
    db = tmp_path / "memory.db"
    db.write_text("x")
    assert reject_write(db, extra_blocked=[db])
    assert reject_write(tmp_path / "ok.txt", extra_blocked=[db]) is None


def test_coerce_http_url():
    assert coerce_http_url("example.com") == "https://example.com"
    assert coerce_http_url("https://example.com/a") == "https://example.com/a"
    assert coerce_http_url("example.com:8080") == "https://example.com:8080"
    assert coerce_http_url("javascript:alert(1)") is None
    assert coerce_http_url("file:///etc/passwd") is None
    assert coerce_http_url("data:text/html,hi") is None
    assert coerce_http_url("") is None


def test_sanitize_desktop_filename():
    assert sanitize_desktop_filename("foo/bar.txt", ".txt") == "bar.txt"
    assert sanitize_desktop_filename("notes", ".pdf") == "notes.pdf"


def test_runtime_pause_and_stop():
    reset()
    try:
        resume()
        assert not is_paused()
        assert toggle_pause() is True
        assert is_paused()
        assert interrupt_listening()
        assert toggle_pause() is False
        assert not is_paused()
        request_stop()
        assert should_stop()
        assert interrupt_listening()
    finally:
        reset()
