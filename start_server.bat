@echo off
title Digital Signage Server
color 0A
cd /d "C:\DigitalSignageServer"

:MENU
echo Starting Digital Signage Server...
echo.

call signage_env\Scripts\activate

:RESTART
python production_app.py

echo.
echo Server stopped.
echo.
echo 1. Restart server
echo 2. Exit
set /p choice=Enter your choice: 

if "%choice%"=="1" goto RESTART
if "%choice%"=="2" exit
goto MENU
