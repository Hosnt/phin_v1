@echo off
REM Installs Phin into your Windows Startup folder so it launches
REM automatically, silently (no console window), every time you log in.
REM Run this ONCE after setup.bat. To undo: delete the shortcut it creates
REM from shell:startup (Win+R -> shell:startup).

set SCRIPT_DIR=%~dp0
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT=%STARTUP_DIR%\Phin.lnk

echo Creating startup shortcut...

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$sc = $ws.CreateShortcut('%SHORTCUT%'); " ^
  "$sc.TargetPath = '%SCRIPT_DIR%.venv\Scripts\pythonw.exe'; " ^
  "$sc.Arguments = 'tray.py'; " ^
  "$sc.WorkingDirectory = '%SCRIPT_DIR%'; " ^
  "$sc.IconLocation = '%SCRIPT_DIR%.venv\Scripts\pythonw.exe'; " ^
  "$sc.Save()"

if exist "%SHORTCUT%" (
    echo Done. Phin will now start automatically on login, running silently
    echo in the background — look for its icon in the system tray.
    echo.
    echo Want it running right now without logging out/in? Run: run_tray.bat
) else (
    echo Something went wrong creating the shortcut. You can also just
    echo manually copy a shortcut to "%STARTUP_DIR%" pointing at:
    echo   %SCRIPT_DIR%.venv\Scripts\pythonw.exe tray.py
)
pause
