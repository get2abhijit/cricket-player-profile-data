@echo off
setlocal
cd /d %~dp0\..
.venv\Scripts\python.exe tools\run_clean_pipeline.py %*
endlocal
