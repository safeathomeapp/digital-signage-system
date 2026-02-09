@echo off
title Reset Admin PIN
color 0A

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Virtual environment not found.
    echo Please run setup_server.ps1 first.
    echo.
    pause
    exit /b 1
)

echo Starting server with temporary PIN 1234...
set SIGNAGE_ADMIN_PIN=1234
".venv\Scripts\python.exe" production_app.py
