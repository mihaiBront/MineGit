@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "BUILD_VENV=%SCRIPT_DIR%.venv-build-win"
set "REQUIREMENTS=%SCRIPT_DIR%src\requirements.txt"
set "MAIN_FILE=%SCRIPT_DIR%src\MineGit.py"
set "APP_NAME=MineGit"
set "DIST_DIR=%SCRIPT_DIR%dist"
set "WORK_DIR=%SCRIPT_DIR%build\pyinstaller-win"
set "SPEC_DIR=%SCRIPT_DIR%build\pyinstaller-spec-win"

if not exist "%BUILD_VENV%\Scripts\python.exe" (
    echo [build_exe] Creating build virtual environment...
    py -3 -m venv "%BUILD_VENV%" 2>nul
    if errorlevel 1 (
        python -m venv "%BUILD_VENV%"
    )
)

echo [build_exe] Upgrading pip...
"%BUILD_VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [build_exe] Installing dependencies...
"%BUILD_VENV%\Scripts\python.exe" -m pip install -r "%REQUIREMENTS%" pyinstaller
if errorlevel 1 goto :error

if exist "%WORK_DIR%" rmdir /s /q "%WORK_DIR%"
if exist "%SPEC_DIR%" rmdir /s /q "%SPEC_DIR%"

echo [build_exe] Building %APP_NAME%.exe with PyInstaller...
"%BUILD_VENV%\Scripts\pyinstaller.exe" ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "%APP_NAME%" ^
  --distpath "%DIST_DIR%" ^
  --workpath "%WORK_DIR%" ^
  --specpath "%SPEC_DIR%" ^
  "%MAIN_FILE%"
if errorlevel 1 goto :error

echo [build_exe] Done. EXE available at:
echo %DIST_DIR%\%APP_NAME%.exe
exit /b 0

:error
echo [build_exe] Build failed.
exit /b 1
