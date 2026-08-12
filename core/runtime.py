"""
Process-wide run flags so the tray, voice loop, and wake-word listener
share the same pause/stop state.

tray.py used to flip a private Event that run_voice_loop() never checked,
so "Pause Listening" did nothing until the whole loop crashed and restarted.
"""
import threading

_paused = threading.Event()
_stop = threading.Event()


def pause() -> None:
    _paused.set()


def resume() -> None:
    _paused.clear()


def is_paused() -> bool:
    return _paused.is_set()


def toggle_pause() -> bool:
    """Returns True if Phin is now paused."""
    if _paused.is_set():
        _paused.clear()
        return False
    _paused.set()
    return True


def request_stop() -> None:
    _stop.set()


def should_stop() -> bool:
    return _stop.is_set()


def interrupt_listening() -> bool:
    """True when the wake-word loop should drop out of the mic read."""
    return _paused.is_set() or _stop.is_set()


def reset() -> None:
    """Clear both flags. Used by tests; not needed at runtime."""
    _paused.clear()
    _stop.clear()
