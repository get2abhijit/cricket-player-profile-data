@echo off
setlocal
cd /d %~dp0\..
.venv\Scripts\python.exe tools\verify_dashboard_counts.py %*
endlocal
