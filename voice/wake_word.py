"""
Wake word detection — openWakeWord (a real, purpose-built detector model),
NOT continuous Whisper transcription.

Why this replaced the previous approach: transcribing every noise burst with
Whisper and string-matching "phin/finn/fin/pin" against the text was both
SLOW (a full Whisper pass every ~1-3s, competing with the CPU you need for
the actual command afterward) and INACCURATE (those are common phonemes —
random speech/noise kept "hearing" a wake word that wasn't said). openWakeWord
runs a tiny dedicated ONNX model at ~10ms per 80ms audio chunk — an order of
magnitude faster, and it's actually trained to reject non-wake-word speech.

Trade-off: openWakeWord ships pretrained models ("hey_jarvis", "alexa",
"hey_mycroft") but not a "Hey Phin" model — training a custom one takes
30-60 min with their notebook (openWakeWord/notebooks/automatic_model_training.ipynb).
Until you do that, Phin wakes on "Hey Jarvis" by default (configurable via
WAKE_WORD_MODEL in .env — you can drop a trained "hey_phin.onnx" there once
you have one and switch to it with zero code changes).
"""
import pathlib
import numpy as np
import sounddevice as sd
import openwakeword.utils
from openwakeword.model import Model

from voice.audio_devices import resolve_device
from core.config import Config

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # openWakeWord expects 80ms chunks at 16kHz
DETECTION_THRESHOLD = 0.5

_model = None
_download_attempted = False

REQUIRED_MODEL_FILES = [
    "melspectrogram.onnx",
    "embedding_model.onnx",
    "silero_vad.onnx",
    "hey_jarvis_v0.1.onnx",
]


def _models_present() -> bool:
    # Resolve the actual install location robustly instead of guessing a path.
    import openwakeword
    real_dir = pathlib.Path(openwakeword.__file__).parent / "resources" / "models"
    return all((real_dir / f).exists() for f in REQUIRED_MODEL_FILES)


def _get_model() -> Model:
    global _model, _download_attempted
    if _model is None:
        wake_word_name = Config.WAKE_WORD_MODEL or "hey_jarvis"

        if not _models_present():
            if _download_attempted:
                # Already tried and failed this run — don't hammer a dead
                # connection every single loop iteration. Fail fast and
                # clearly instead of a wall of retry tracebacks.
                raise RuntimeError(
                    "openWakeWord model files are still missing and the last download "
                    "attempt failed. Download them manually (browser networking often "
                    "works even when this fails) and place them in the models folder "
                    "— see README.md 'Manual wake-word model download' for exact links."
                )
            _download_attempted = True
            try:
                openwakeword.utils.download_models()
            except Exception as e:
                raise RuntimeError(
                    "Couldn't auto-download openWakeWord's model files "
                    f"(network error: {e}). Download them manually in your browser "
                    "instead — see README.md 'Manual wake-word model download' for "
                    "the exact 4 URLs and where to put them."
                ) from None

        # inference_framework="onnx" is required here — without it, openWakeWord
        # tries to also load a .tflite variant of the model first and throws
        # (tflite_runtime isn't installed, and doesn't need to be: onnxruntime,
        # already in requirements.txt, does the exact same job).
        _model = Model(wakeword_models=[wake_word_name], inference_framework="onnx")
    return _model


def wait_for_wake_word(level_cb=None, abort_cb=None) -> str | None:
    """Blocks until the wake word is detected. Returns the model name that fired,
    or None if abort_cb() becomes true (pause / quit from the tray).

    level_cb(volume), if given, is called on every ~80ms chunk with raw mic
    energy, so a caller (main.py -> HUD) can show a live "is the mic picking
    anything up" indicator instead of looking dead while it's listening.
    """
    model = _get_model()
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                         device=resolve_device()) as stream:
        while True:
            if abort_cb and abort_cb():
                return None
            chunk, _ = stream.read(CHUNK_SIZE)
            audio = chunk.flatten().astype(np.int16)
            if level_cb:
                level_cb(float(np.abs(audio).mean()) / 32768.0)
            predictions = model.predict(audio)
            for name, score in predictions.items():
                if score > DETECTION_THRESHOLD:
                    model.reset()  # clear internal state so it doesn't immediately re-fire
                    return name
