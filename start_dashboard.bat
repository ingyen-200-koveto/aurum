@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo HIBA: A .venv nem talalhato a projekt mappajaban.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" start_dashboard.py
pause
