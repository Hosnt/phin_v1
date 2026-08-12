# Phin — personal Jarvis-style assistant

A voice assistant that lives on your Windows PC: wake word → listens → thinks
(Claude, GPT, or a local free proxy) → controls the computer / writes files /
remembers things → talks back in an ElevenLabs voice.

## Wake word

Say **“Hey Jarvis”**. That is openWakeWord’s pretrained model. There is no
off-the-shelf “Hey Phin” model yet — train one later (see
`voice/wake_word.py`) and set `WAKE_WORD_MODEL` in `.env`.

## ⚠️ Rotate leaked keys

An earlier upload of this project included a live `.env` (ElevenLabs and
possibly others) inside a zip committed to git. **Treat those keys as
compromised.** Regenerate them in each provider’s dashboard and put the new
values only in a local `.env` that is gitignored.

Never paste real keys into chat, commit them, or hardcode them in source.

## Architecture

```
main.py                  orchestrator: wake word -> STT -> LLM -> tools -> TTS
tray.py                  system-tray host (pause / dashboard / quit)
core/
  config.py              loads .env
  runtime.py             shared pause/stop flags (tray <-> voice loop)
  safety.py              app-name / path / URL guards used by tools
  llm_provider.py        Anthropic / OpenAI / fallback
  llm_proxy.py           auto-starts local freellmpool if configured
  tool_registry.py       tool schemas + dispatch
  memory.py              SQLite conversation log + durable facts
tools/
  computer.py            open apps, screenshot, click/type/hotkeys
  files.py               create .txt / .docx / .pdf on the Desktop
  browser.py             open URLs, tabs, search — http(s) only
  code_editor.py         read/write/rewrite files (system paths blocked)
voice/
  wake_word.py           openWakeWord ("Hey Jarvis")
  stt.py                 faster-whisper, local
  tts.py                 ElevenLabs
ui/
  overlay.html           HUD
  server.py              Flask-SocketIO bridge
  native_overlay.py      frameless always-on-top orb (pywebview)
```

## Setup (Windows)

1. **Python 3.11+**, then:

   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   Or double-click `setup.bat`.

2. Copy `.env.example` to `.env` and fill it in:

   - **No paid LLM key?** Default is `LLM_PROVIDER=openai` pointing at a local
     [freellmpool](https://github.com/0xzr/freellmpool) proxy:

     ```
     pip install freellmpool
     freellmpool init --yes
     freellmpool proxy
     ```

     Leave the proxy running. Phin also tries to start it if
     `OPENAI_BASE_URL` is localhost.

   - **Anthropic later:** set `ANTHROPIC_API_KEY` and `LLM_PROVIDER=anthropic`.

   - `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` — required for voice mode.
     Premade voices (e.g. Rachel) work on the free tier; Voice Library IDs
     return 402.

   - `DESKTOP_PATH` — your real Desktop, e.g. `C:\Users\yourname\Desktop`.

   - `GEMINI_API_KEY` — only needed for `describe_screen` (vision).

3. **Text mode first** (no mic):

   ```
   python main.py text
   ```

   Or `run_text.bat`. Try: `open notepad`, `take a screenshot`,
   `write a text file called test.txt that says hello`,
   `remember that my favorite editor is VS Code`.

4. **Voice mode** once text works:

   ```
   python main.py voice
   python main.py voice --ui        # HUD in a browser tab
   python main.py voice --native    # floating desktop orb
   ```

   Or `run_voice.bat`. If it never hears you: `python main.py list-mics`
   then set `MIC_DEVICE` in `.env`.

5. **Tray / start with Windows:**

   ```
   python tray.py          # or run_tray.bat
   install_startup.bat     # once — silent launch on login
   ```

   Tray menu: Show Dashboard, Pause / Resume Listening, Quit.

6. **HUD preview only:** `python ui/server.py` then open
   `http://localhost:5151`.

## Manual wake-word model download

`voice/wake_word.py` auto-downloads openWakeWord models on first run. If that
fails (some firewalls reset Python’s connection to GitHub), download these
in a browser and put them in
`.venv\Lib\site-packages\openwakeword\resources\models\`:

- https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx
- https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx
- https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/silero_vad.onnx
- https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.onnx

## What’s real vs. what’s next

- Working: text + voice loops, tool calling, memory, ElevenLabs TTS, local
  Whisper STT, openWakeWord, HUD / native orb, tray + Windows startup.
- Not built: Gmail / Notion / Google Drive (each needs its own OAuth).

## Security

- `.env` is gitignored. Do not commit it.
- `open_app` no longer runs a shell string. App names are restricted to
  letters, numbers, spaces, dots, and dashes.
- Desktop file tools strip directory components so `..\..\Windows\...`
  cannot escape `DESKTOP_PATH`.
- `write_file` / `find_replace_in_file` / `append_to_file` refuse `.env`,
  `.git`, `.ssh`, and Windows/POSIX system trees. They can still overwrite
  ordinary project files — that is the point of voice code editing. Keep
  those projects in git.
- `open_url` only accepts `http://` and `https://`.
- Computer-control tools still perform real OS actions. A wrong
  transcription can still close a window or type into the focused app.

## Tests

```
pip install pytest
python -m pytest tests -q
```
