@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "REQ_FILE=%SCRIPT_DIR%src\requirements.txt"
set "APP_FILE=%SCRIPT_DIR%src\MineGit.py"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    py -3 -m venv "%VENV_DIR%" 2>nul
    if errorlevel 1 (
        python -m venv "%VENV_DIR%"
    )
)

"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%REQ_FILE%"
"%VENV_DIR%\Scripts\python.exe" "%APP_FILE%"
