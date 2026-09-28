@echo off
taskkill /F /IM copilot_listener.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
echo Copilot Listener and any active sessions have been stopped.
timeout /t 2 >nul
