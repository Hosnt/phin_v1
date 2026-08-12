"""
Text-to-speech for Phin's voice, via ElevenLabs.
"""
import os
import tempfile
from elevenlabs.client import ElevenLabs
from core.config import Config

_client = None

# ElevenLabs "premade" voices work on the free API tier. Voice Library
# (community/shared) voices do NOT — the API returns 402 payment_required
# for those regardless of the voice_id in .env. Rachel is ElevenLabs' own
# default premade voice and is used here as the safe fallback.
_FREE_TIER_FALLBACK_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel (premade)
_warned_about_voice_downgrade = False


def _get_client() -> ElevenLabs:
    global _client
    if _client is None:
        _client = ElevenLabs(api_key=Config.ELEVENLABS_API_KEY)
    return _client


def _play_bytes(audio_bytes: bytes):
    """
    Play raw audio bytes. Tries the elevenlabs package's own helper first
    (its import path/shape has changed across SDK versions, so we probe a
    couple of locations), then falls back to just handing the file to
    Windows' default player so speech always plays even if the SDK's
    playback helper breaks again in a future version.
    """
    try:
        from elevenlabs.play import play as _play  # newer SDK layout
        _play(audio_bytes)
        return
    except Exception:
        pass
    try:
        import elevenlabs as _el
        _play = getattr(_el, "play", None)
        if callable(_play):
            _play(audio_bytes)
            return
    except Exception:
        pass

    # Fallback: write to a temp mp3 and open with the OS default player.
    fd, path = tempfile.mkstemp(suffix=".mp3")
    with os.fdopen(fd, "wb") as f:
        f.write(audio_bytes)
    os.startfile(path)  # Windows-only, matches the rest of this project


def _synthesize(text: str, voice_id: str) -> bytes:
    client = _get_client()
    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id="eleven_turbo_v2_5",
        text=text,
        output_format="mp3_44100_128",
    )
    return b"".join(audio) if hasattr(audio, "__iter__") and not isinstance(audio, (bytes, bytearray)) else audio


def speak(text: str):
    """Convert text to speech and play it out loud."""
    global _warned_about_voice_downgrade
    if not text.strip():
        return
    try:
        audio_bytes = _synthesize(text, Config.ELEVENLABS_VOICE_ID)
        _play_bytes(audio_bytes)
    except Exception as e:
        err_str = str(e)
        is_library_voice_402 = "402" in err_str and (
            "paid_plan_required" in err_str or "Free users cannot use library voices" in err_str
        )
        if is_library_voice_402 and Config.ELEVENLABS_VOICE_ID != _FREE_TIER_FALLBACK_VOICE_ID:
            if not _warned_about_voice_downgrade:
                print(
                    "  [warn] ELEVENLABS_VOICE_ID in .env is a Voice Library voice, which "
                    "ElevenLabs blocks via the API on free-tier accounts (this is an account "
                    "restriction, not a bug). Falling back to the free premade voice 'Rachel' "
                    "for this session. To use your original voice for free: get it from "
                    "ElevenLabs' own Default/premade voices instead of the Voice Library, or "
                    "upgrade your ElevenLabs plan. Update ELEVENLABS_VOICE_ID in .env to "
                    f"'{_FREE_TIER_FALLBACK_VOICE_ID}' to stop seeing this fallback."
                )
                _warned_about_voice_downgrade = True
            try:
                audio_bytes = _synthesize(text, _FREE_TIER_FALLBACK_VOICE_ID)
                _play_bytes(audio_bytes)
                return
            except Exception as e2:
                print(f"  [warn] TTS fallback also failed, continuing in text-only: {e2}")
                return
        print(f"  [warn] TTS failed, continuing in text-only: {e}")
