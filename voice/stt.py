"""
Speech-to-text using faster-whisper (runs locally, no API key needed).

Accuracy improvements over a bare whisper call:
  - "small.en" model instead of "base.en" — meaningfully fewer misheard words,
    still runs fine on CPU for a single user talking to their PC.
  - Whisper's own built-in VAD (Silero) trims silence/noise before decoding,
    instead of a naive energy threshold, which cuts a lot of misrecognition
    caused by feeding the model dead air or background hum.
  - One-time ambient noise calibration at startup so the "are they still
    talking" cutoff adapts to the room instead of a hardcoded guess.
  - Per-segment confidence (avg_logprob + no_speech_prob) is checked; low
    confidence or clearly-garbled results return None so main.py can ask
    "Sorry, I didn't catch that — could you repeat that?" instead of silently
    acting on a wrong transcription.
"""
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from voice.audio_devices import resolve_device

_model = None
SAMPLE_RATE = 16000

# Tuned by calibrate_noise_floor() at startup; sensible default until then.
_silence_threshold = 0.012

# Below this confidence, treat the transcription as unreliable.
MIN_AVG_LOGPROB = -1.0
MAX_NO_SPEECH_PROB = 0.6


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        # "small.en" trades a bit of speed for noticeably better accuracy
        # than "base.en", especially on names, filenames, and URLs.
        _model = WhisperModel("small.en", device="cpu", compute_type="int8")
    return _model


def calibrate_noise_floor(seconds: float = 1.2) -> float:
    """Sample ambient room noise once at startup so the silence cutoff isn't
    a blind guess. Call this once when Phin boots, before the main loop."""
    global _silence_threshold
    print("Calibrating microphone to room noise... stay quiet for a second.")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                         device=resolve_device()) as stream:
        chunk, _ = stream.read(int(SAMPLE_RATE * seconds))
    noise_floor = float(np.abs(chunk).mean())
    # Speech needs to clear the noise floor by a healthy margin.
    _silence_threshold = max(0.008, noise_floor * 3.5)
    print(f"Mic calibrated (silence threshold: {_silence_threshold:.4f}).")
    return _silence_threshold


def get_silence_threshold() -> float:
    """Current calibrated silence/speech cutoff, so other modules (wake_word,
    the HUD) can tell "is this chunk actually speech" without duplicating
    the calibration logic."""
    return _silence_threshold


def record_until_silence(max_seconds: int = 10, silence_duration: float = 0.9,
                          level_cb=None) -> np.ndarray:
    """Record from the mic until the user stops talking (energy-based endpointing;
    Whisper's own VAD does the fine-grained speech/silence work during transcription).

    level_cb(volume), if given, is called on every ~100ms chunk with the raw
    mic energy for that chunk — lets a caller show a live "is Phin actually
    hearing me" indicator instead of the UI just sitting there silently
    while it records.
    """
    frames = []
    silence_chunks = 0
    speech_detected = False
    chunk_size = int(SAMPLE_RATE * 0.1)
    max_chunks = int(max_seconds / 0.1)
    silence_chunks_needed = int(silence_duration / 0.1)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                         device=resolve_device()) as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(chunk_size)
            frames.append(chunk.copy())
            volume = float(np.abs(chunk).mean())
            if level_cb:
                level_cb(volume)

            if volume >= _silence_threshold:
                speech_detected = True
                silence_chunks = 0
            elif speech_detected:
                silence_chunks += 1
                if silence_chunks >= silence_chunks_needed:
                    break

    return np.concatenate(frames, axis=0).flatten()


def transcribe(audio: np.ndarray) -> tuple[str | None, float]:
    """Returns (text, confidence_0_to_1). text is None if confidence was too low
    or nothing intelligible was heard, so the caller can ask the user to repeat."""
    model = _get_model()
    segments, info = model.transcribe(
        audio,
        language="en",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        beam_size=5,
        condition_on_previous_text=False,  # avoids compounding errors across segments
    )

    texts = []
    logprobs = []
    no_speech_probs = []
    for seg in segments:
        texts.append(seg.text.strip())
        logprobs.append(seg.avg_logprob)
        no_speech_probs.append(seg.no_speech_prob)

    full_text = " ".join(t for t in texts if t).strip()
    if not full_text:
        return None, 0.0

    avg_logprob = sum(logprobs) / len(logprobs) if logprobs else -999
    avg_no_speech = sum(no_speech_probs) / len(no_speech_probs) if no_speech_probs else 1.0

    # Rough confidence heuristic: 0 (garbage) to 1 (confident).
    confidence = max(0.0, min(1.0, 1.0 + avg_logprob)) * (1.0 - avg_no_speech)

    if avg_logprob < MIN_AVG_LOGPROB or avg_no_speech > MAX_NO_SPEECH_PROB:
        return None, confidence

    return full_text, confidence


def listen_and_transcribe(max_retries: int = 1, level_cb=None) -> str | None:
    """Records + transcribes, automatically re-prompting once on low confidence
    instead of silently guessing wrong. Returns None if still unclear after retries."""
    for attempt in range(max_retries + 1):
        audio = record_until_silence(level_cb=level_cb)
        if len(audio) < SAMPLE_RATE * 0.3:  # too short to contain real speech
            return None
        text, confidence = transcribe(audio)
        if text:
            return text
        if attempt < max_retries:
            print("  [stt] low confidence, listening again...")
    return None
