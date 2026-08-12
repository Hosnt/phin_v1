"""
Phin — personal voice assistant.

Loop:
  1. Wait for wake word ("Hey Jarvis" by default — see voice/wake_word.py to customize)
  2. Record + transcribe what you say
  3. Send to the LLM (with memory + tools available)
  4. Execute any tool calls (open apps, screenshots, files, remember/recall...)
  5. Speak the reply out loud
  6. Log the turn to memory, go back to step 1

Usage:
  python main.py text              # keyboard-only, no mic/wake-word needed
  python main.py voice             # full voice loop
  python main.py voice --ui        # voice loop + live HUD in a browser tab at http://localhost:5151
  python main.py voice --native    # voice loop + HUD as a real floating desktop orb overlay (not a browser tab)
  python main.py text --native     # text loop + native overlay (handy for testing the UI without a mic)
  python main.py list-mics         # list input devices sounddevice can see, to fix "Phin isn't hearing me"
"""
import sys
import threading
import time
import traceback

from core.config import Config
from core.memory import Memory
from core.llm_provider import get_provider
from core.tool_registry import TOOLS, dispatch
from core import llm_proxy, runtime
from voice import wake_word, stt, tts

SYSTEM_PROMPT_TEMPLATE = """You are {name}, an AI assistant running locally on the user's \
Windows PC, controlling the machine directly by voice with no mouse or keyboard from the \
user. You can open apps, control browser tabs, read and rewrite code/text files on disk, \
take screenshots, and remember things — all via tools.

Voice and tone:
- Calm, precise, efficient. Minimal words, maximum clarity. Slightly formal, never verbose.
- Address the user as "sir" — naturally, at the start or end of a sentence, not in every line.
- Default to short replies (1-4 sentences). Only expand if explicitly asked for more detail.
- No filler, no repetition, no emojis, no casual tone. Do not roleplay theatrically.
- If the user's approach is inefficient or wrong, say so plainly and recommend better:
  "That approach is suboptimal, sir. I recommend ..."
- Answer directly, then add one concise recommendation if it's useful. Nothing more.

Rules for editing/rewriting files: always read_file first if the file already exists, \
so you know what you're changing. Prefer find_replace_in_file for small, targeted edits \
and only use write_file to replace a whole file's contents when the user clearly wants \
a full rewrite. For anything destructive or hard to undo (overwriting a file with new \
content, closing a tab with unsaved work, deleting/replacing large chunks of code), \
briefly confirm what you're about to do before doing it, unless the user was already \
explicit and unambiguous about it.

If a transcribed command looks garbled, cut off, or doesn't make sense as a real request, \
ask the user to repeat it rather than guessing what they meant and taking action.

DO NOT call any tool for casual greetings, chit-chat, filler ("hey", "sup", "bruh", "lol", \
"ok", "thanks"), or input that has no clear actionable request — just reply conversationally \
and, if it's genuinely unclear what they want, ask what they'd like help with. Never guess \
at a website, app, or file to open unless the user actually named one or something \
equivalent (e.g. "check my email" -> Gmail is a reasonable, explicit request; "hey" or \
"bruh" is not a request for anything).

CRITICAL — never fabricate: You have no tool that reads the contents of any online account \
(email, calendar, school/work portals, etc.) — you can only OPEN a browser tab to a site via \
open_url/search_web, you cannot see what's inside it unless you then use describe_screen. \
NEVER claim to have checked, read, or found specific information (meeting names, times, \
emails, grades, assignments) unless a tool call in this exact conversation actually returned \
that data. If the user asks about something you have no tool for, say so plainly and only \
open a relevant site if they've actually named or clearly implied which one — don't default \
to any particular site as a fallback action. describe_screen is the one exception to "can't \
see inside it" — after opening a site, you can use describe_screen to actually look at what's \
rendered on screen and report only what you genuinely see there.

Known facts about the user:
{facts}
"""

# Set in __main__ if --ui is passed; kept as a no-op stub otherwise so the
# rest of the code never has to check "is the HUD running?" itself.
_hud = None


class _NullHud:
    def status(self, *a, **k): pass
    def transcript(self, *a, **k): pass
    def hearing(self, *a, **k): pass


class _LiveHud:
    def __init__(self):
        from ui import server as ui_server
        self._server = ui_server
        ui_server.start_in_background()
        self._last_hearing = None

    def status(self, state, text=""):
        self._server.push_status(state, text)

    def transcript(self, text, speaker="user"):
        self._server.push_transcript(text, speaker)

    def hearing(self, active: bool):
        # Dedup so a steady stream of ~10/sec mic-level samples doesn't spam
        # the socket with an identical event every single chunk.
        if active == self._last_hearing:
            return
        self._last_hearing = active
        self._server.push_hearing(active)


def _mic_level_relay(volume: float):
    """Turns a raw mic-energy sample into the 'is Phin actually hearing
    speech right now' indicator the HUD shows under the orb."""
    _hud.hearing(volume >= stt.get_silence_threshold())


def build_system_prompt(memory: Memory) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(name=Config.ASSISTANT_NAME, facts=memory.facts_as_context())


def handle_conversation_turn(user_text: str, memory: Memory, provider):
    memory.add_turn("user", user_text)
    messages = memory.recent_turns(limit=20)
    system = build_system_prompt(memory)

    _hud.status("thinking", "THINKING")

    # Agentic loop: keep calling the LLM until it stops requesting tools.
    for _ in range(6):
        resp = provider.chat(messages, TOOLS, system)
        messages.append(provider.assistant_message(resp))

        if not resp.tool_calls:
            if resp.text:
                print(f"{Config.ASSISTANT_NAME}: {resp.text}")
                _hud.transcript(resp.text, speaker="assistant")
                _hud.status("speaking", "SPEAKING")
                try:
                    tts.speak(resp.text)
                except Exception as e:
                    print(f"  [warn] TTS failed, continuing in text-only: {e}")
                memory.add_turn("assistant", resp.text)
            _hud.status("idle", "STANDING BY")
            return

        for tc in resp.tool_calls:
            print(f"  [tool] {tc.name}({tc.input})")
            _hud.status("tool", f"RUNNING {tc.name.upper()}")
            result = dispatch(tc.name, tc.input, memory)
            messages.append(provider.tool_result_message(tc.id, tc.name, result))
        _hud.status("thinking", "THINKING")

    msg = "Stopped after too many tool steps — something may be looping."
    print(f"{Config.ASSISTANT_NAME}: {msg}")
    _hud.transcript(msg, speaker="assistant")
    _hud.status("idle", "STANDING BY")


def run_voice_loop():
    problems = Config.validate(require_voice=True)
    if problems:
        print("Configuration problems found in .env:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    memory = Memory()
    provider = get_provider()

    llm_proxy.ensure_running_for_config()
    stt.calibrate_noise_floor()

    print(f"{Config.ASSISTANT_NAME} is online. Listening for \"Hey Jarvis\"...")
    _hud.status("idle", "STANDING BY")

    while not runtime.should_stop():
        try:
            if runtime.is_paused():
                _hud.status("idle", "PAUSED")
                time.sleep(0.4)
                continue

            detected = wake_word.wait_for_wake_word(
                level_cb=_mic_level_relay,
                abort_cb=runtime.interrupt_listening,
            )
            if not detected or runtime.interrupt_listening():
                continue

            print("Wake word detected. Listening...")
            _hud.hearing(False)
            _hud.status("listening", "LISTENING")
            tts.speak("Yes?")

            user_text = stt.listen_and_transcribe(max_retries=1, level_cb=_mic_level_relay)
            _hud.hearing(False)
            if not user_text:
                print("  [stt] couldn't understand, going back to standby.")
                tts.speak("Sorry, I didn't catch that.")
                _hud.status("idle", "STANDING BY")
                continue
            print(f"You: {user_text}")
            _hud.transcript(user_text, speaker="user")

            if user_text.strip().lower() in ("stop", "shut down", "exit", "quit"):
                tts.speak("Going offline.")
                _hud.status("idle", "OFFLINE")
                break

            handle_conversation_turn(user_text, memory, provider)

        except KeyboardInterrupt:
            print("\nShutting down.")
            break
        except Exception:
            # One bad turn (mic glitch, provider hiccup, tool crash) should
            # never take the whole assistant down — but it also shouldn't
            # spam-retry with zero delay if the same error keeps happening
            # (e.g. a missing dependency), so a short pause goes here.
            print("  [error] turn failed, recovering:")
            traceback.print_exc()
            _hud.hearing(False)
            _hud.status("idle", "ERROR — RECOVERED")
            time.sleep(1.5)


def run_text_loop():
    """Text-only mode for testing without a mic/wake word set up."""
    problems = Config.validate()
    if problems:
        print("Configuration problems found in .env:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    memory = Memory()
    provider = get_provider()
    llm_proxy.ensure_running_for_config()
    print(f"{Config.ASSISTANT_NAME} (text mode). Type 'exit' to quit.")
    _hud.status("idle", "STANDING BY")

    while True:
        try:
            user_text = input("You: ").strip()
            if user_text.lower() in ("exit", "quit"):
                break
            if not user_text:
                continue
            _hud.transcript(user_text, speaker="user")
            handle_conversation_turn(user_text, memory, provider)
        except KeyboardInterrupt:
            print("\nShutting down.")
            break
        except Exception:
            print("  [error] turn failed, recovering:")
            traceback.print_exc()
            _hud.status("idle", "ERROR — RECOVERED")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "text"

    if mode == "list-mics":
        from voice.audio_devices import print_input_devices
        print_input_devices()
        sys.exit(0)

    use_native = "--native" in sys.argv
    use_ui = use_native or "--ui" in sys.argv

    _hud = _LiveHud() if use_ui else _NullHud()
    loop_fn = run_voice_loop if mode == "voice" else run_text_loop

    if use_native:
        # pywebview has to own the main thread on Windows, so the actual
        # assistant loop (mic/wake-word or text input) runs in the
        # background and the native orb overlay blocks in front.
        threading.Thread(target=loop_fn, daemon=True).start()
        from ui import native_overlay
        native_overlay.launch()
    else:
        loop_fn()
