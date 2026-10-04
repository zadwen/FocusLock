@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3.10 or newer from https://www.python.org/downloads/windows/
  exit /b 1
)
py -3 -m venv .venv-build
if errorlevel 1 exit /b 1
".venv-build\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
".venv-build\Scripts\python.exe" scripts\build.py
if errorlevel 1 exit /b 1
echo Ready: dist\FocusLock.exe
