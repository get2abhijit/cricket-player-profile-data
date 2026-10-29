@echo off
setlocal
cd /d %~dp0\..
.venv\Scripts\python.exe tools\run_automation.py run-7d %*
endlocal
