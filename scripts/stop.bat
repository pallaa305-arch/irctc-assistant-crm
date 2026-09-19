@echo off
echo Stopping IRCTC Assistant services...
taskkill /F /IM uvicorn.exe /T 2>nul
taskkill /F /IM node.exe /T 2>nul
echo All services stopped cleanly.
pause
