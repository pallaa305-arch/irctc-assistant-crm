@echo off
echo =========================================================
echo  Setting up 24/7 Windows Auto-Start for IRCTC Assistant
echo =========================================================

set SCRIPT_DIR=%~dp0
set TARGET_VBS=%SCRIPT_DIR%run_background.vbs
set SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\IRCTC_Assistant.lnk

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%TARGET_VBS%\"'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo [SUCCESS] Auto-Start shortcut added to Windows Startup!
    echo Every time you turn on your PC, the bot will automatically run silently in the background.
) else (
    echo [ERROR] Failed to create shortcut.
)
pause
