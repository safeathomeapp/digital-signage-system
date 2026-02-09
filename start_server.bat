@echo off
title Digital Signage Server
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

:MENU
echo Starting Digital Signage Server...
echo.

:RESTART
".venv\Scripts\python.exe" production_app.py

echo.
echo Server stopped.
echo.
echo 1. Restart server
echo 2. Exit
set /p choice=Enter your choice: 

if "%choice%"=="1" goto RESTART
if "%choice%"=="2" exit
goto MENU
