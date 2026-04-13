@echo off
setlocal
cd /d %~dp0\..
.venv\Scripts\python.exe tools\run_second_pass_fast.py %*
endlocal
