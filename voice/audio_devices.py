"""
Input-device discovery + selection.

The "no response" symptom (mic calibrates fine, wake word model loads and
Phin says it's "online. Listening..." — but it never actually hears you) is
almost always sounddevice recording from the wrong DEFAULT input device:
a webcam mic, a virtual cable, a Bluetooth headset that's connected but not
the active input, etc. Every `sd.InputStream()` call in this project used to
leave `device` unset, which just grabs whatever Windows currently calls
"default" — silently, with no error, so Phin looks alive while deaf.

Fix: set MIC_DEVICE in .env to pin an explicit device —
  MIC_DEVICE=3            # exact device index
  MIC_DEVICE=Realtek      # substring match against the device name
Leave it blank to keep using the OS default (fine once you've confirmed
that's actually the right mic).

Run `python main.py list-mics` to see every input device sounddevice can
see, with the current OS default and current MIC_DEVICE match both marked.
"""
import sounddevice as sd

from core.config import Config

_resolved_device = "unset"  # sentinel so None (=OS default) is cacheable too


def list_input_devices() -> list[dict]:
    devices = sd.query_devices()
    try:
        default_idx = sd.default.device[0]
    except Exception:
        default_idx = None
    return [
        {
            "index": i,
            "name": d["name"],
            "channels": d["max_input_channels"],
            "default": i == default_idx,
        }
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


def _matches_configured(d: dict) -> bool:
    configured = (Config.MIC_DEVICE or "").strip()
    if not configured:
        return d["default"]
    if configured.isdigit():
        return d["index"] == int(configured)
    return configured.lower() in d["name"].lower()


def print_input_devices():
    devices = list_input_devices()
    if not devices:
        print("No input devices found by sounddevice — check your OS mic permissions.")
        return
    print("Available microphones:")
    for d in devices:
        tags = []
        if d["default"]:
            tags.append("OS default")
        if _matches_configured(d):
            tags.append("Phin will use this")
        tag_str = f"  <- {', '.join(tags)}" if tags else ""
        print(f"  [{d['index']}] {d['name']}{tag_str}")
    print('\nSet MIC_DEVICE in .env (an index above, or a substring of a name) to pin one.')


def resolve_device():
    """Returns a sounddevice `device=` value (index, or None for OS default),
    resolved once and cached. Call this from stt.py / wake_word.py instead of
    leaving `device` unset."""
    global _resolved_device
    if _resolved_device != "unset":
        return _resolved_device

    configured = (Config.MIC_DEVICE or "").strip()
    if not configured:
        _resolved_device = None
        return None

    if configured.isdigit():
        _resolved_device = int(configured)
        return _resolved_device

    for d in list_input_devices():
        if configured.lower() in d["name"].lower():
            print(f"[mic] Using input device [{d['index']}] {d['name']} "
                  f"(matched MIC_DEVICE='{configured}')")
            _resolved_device = d["index"]
            return _resolved_device

    print(f"  [warn] MIC_DEVICE='{configured}' didn't match any input device; "
          f"falling back to OS default. Run `python main.py list-mics` to see options.")
    _resolved_device = None
    return None
