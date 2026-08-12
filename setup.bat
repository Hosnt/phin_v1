@echo off
REM One-time setup: creates a venv and installs everything.
echo === Setting up Phin ===

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Install Python 3.11+ from https://www.python.org/downloads/ and re-run this.
    pause
    exit /b 1
)

python -m venv .venv
call .venv\Scripts\activate.bat

echo Installing dependencies (this can take a few minutes)...
pip install --upgrade pip
pip install -r requirements.txt

if not exist ".env" (
    copy .env.example .env
    echo Created .env from .env.example — open it and fill in your keys before running Phin.
) else (
    echo .env already exists, leaving it alone.
)

echo.
echo === Setup complete ===
echo Next: edit .env with your keys, then run:
echo   run_text.bat    (test without a mic)
echo   run_voice.bat   (full voice mode)
pause
