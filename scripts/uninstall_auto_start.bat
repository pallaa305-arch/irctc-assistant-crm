@echo off
set SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\IRCTC_Assistant.lnk
if exist "%SHORTCUT_PATH%" (
    del "%SHORTCUT_PATH%"
    echo [SUCCESS] Auto-start removed from Windows Startup.
) else (
    echo Auto-start shortcut not found.
)
pause
