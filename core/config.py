"""
Central configuration for Phin.
Loads everything from .env so no secrets live in source code.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


class Config:
    # Identity
    ASSISTANT_NAME = _get("ASSISTANT_NAME", "Phin")

    # LLM
    LLM_PROVIDER = _get("LLM_PROVIDER", "anthropic").lower()  # "anthropic" | "openai"
    ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = _get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    OPENAI_API_KEY = _get("OPENAI_API_KEY")
    OPENAI_MODEL = _get("OPENAI_MODEL", "gpt-4o")
    OPENAI_BASE_URL = _get("OPENAI_BASE_URL")  # e.g. http://localhost:20128/v1 for OmniRoute

    # Optional: Groq-primary / Gemini-fallback free-tier setup.
    # Set LLM_PROVIDER=fallback to use this instead of a single OPENAI_* config.
    GROQ_API_KEY = _get("GROQ_API_KEY")
    GROQ_MODEL = _get("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_BASE_URL = _get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    GEMINI_API_KEY = _get("GEMINI_API_KEY")
    # gemini-2.5-flash was cut off from new API users and returns 404 now.
    # gemini-3.6-flash is Google's current GA replacement (as of Aug 2026).
    GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-3.6-flash")
    GEMINI_BASE_URL = _get(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    # Ollama — a model running LOCALLY on this PC. Genuinely unlimited (no
    # rate limit, no daily quota, no internet needed after the one-time
    # model download) because nothing leaves the machine. This is the most
    # reliable "free forever" option and is tried FIRST in fallback mode,
    # before burning through Groq/Gemini's daily quotas.
    OLLAMA_ENABLED = _get("OLLAMA_ENABLED", "true").lower() == "true"
    OLLAMA_BASE_URL = _get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OLLAMA_MODEL = _get("OLLAMA_MODEL", "llama3.1:8b")

    # Voice
    ELEVENLABS_API_KEY = _get("ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID = _get("ELEVENLABS_VOICE_ID")
    # openWakeWord model name. No off-the-shelf "Hey Phin" model exists, so
    # this defaults to "hey_jarvis" (say "Hey Jarvis" to wake Phin) until you
    # train a custom one — see voice/wake_word.py for how.
    WAKE_WORD_MODEL = _get("WAKE_WORD_MODEL", "hey_jarvis")
    # Which microphone to use. Blank = OS default (this is what was silently
    # eating your voice before — the OS default input isn't always the mic
    # you think it is). Set to a device index or a substring of its name;
    # run `python main.py list-mics` to see your options.
    MIC_DEVICE = _get("MIC_DEVICE", "")

    # Files
    DESKTOP_PATH = _get("DESKTOP_PATH", str(Path.home() / "Desktop"))

    # Paths
    ROOT_DIR = ROOT_DIR
    DATA_DIR = ROOT_DIR / "data"
    MEMORY_DB = DATA_DIR / "memory.db"

    @classmethod
    def validate(cls, require_voice: bool = False):
        problems = []
        if cls.LLM_PROVIDER == "anthropic" and not cls.ANTHROPIC_API_KEY:
            problems.append("ANTHROPIC_API_KEY is missing in .env (LLM_PROVIDER=anthropic).")
        if cls.LLM_PROVIDER == "openai" and not cls.OPENAI_API_KEY and not cls.OPENAI_BASE_URL:
            problems.append(
                "OPENAI_API_KEY is missing in .env (LLM_PROVIDER=openai). "
                "If you're using a local gateway like OmniRoute or freellmpool, set "
                "OPENAI_BASE_URL instead and OPENAI_API_KEY can stay blank."
            )
        if cls.LLM_PROVIDER == "fallback" and not (cls.OLLAMA_ENABLED or (cls.GROQ_API_KEY and cls.GEMINI_API_KEY)):
            problems.append(
                "LLM_PROVIDER=fallback needs either OLLAMA_ENABLED=true (with Ollama running "
                "locally) or both GROQ_API_KEY and GEMINI_API_KEY set in .env."
            )
        if require_voice and not cls.ELEVENLABS_API_KEY:
            problems.append("ELEVENLABS_API_KEY is missing in .env (required for voice mode).")
        return problems


Config.DATA_DIR.mkdir(parents=True, exist_ok=True)
