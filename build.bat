@echo off
:: FocusLock — Build Script
:: Creates a standalone FocusLock.exe using PyInstaller
:: Run this on Windows with Python + PyInstaller installed

echo ====================================
echo  FocusLock Build Script by zadwen
echo ====================================
echo.

pip install pyinstaller --quiet

pyinstaller ^
  --onefile ^
  --windowed ^
  --name FocusLock ^
  --icon assets/icon.ico ^
  src/focuslock.py

echo.
echo Done! Find FocusLock.exe in the dist/ folder.
pause
