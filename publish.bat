@echo off
setlocal
cd /d "%~dp0"
title Publish open-functional-self-lab

echo ==========================================
echo   open-functional-self-lab  -  one click
echo   equals docs/publish.md steps 0 + 3
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 goto no_python
where git >nul 2>nul
if errorlevel 1 goto no_git

set "PS=powershell"
where powershell >nul 2>nul
if errorlevel 1 set "PS=pwsh"

%PS% -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\publish.ps1" %*
set "CODE=%errorlevel%"

echo.
if not "%CODE%"=="0" goto failed
echo [DONE] pushed to GitHub.
goto end

:no_python
echo [ERROR] python not found in PATH.
echo         Install Python 3.10+ and tick "Add python.exe to PATH".
goto end

:no_git
echo [ERROR] git not found in PATH.
echo         Install Git for Windows, then reopen this window.
goto end

:failed
echo [NOT DONE] exit code %CODE%.
echo Copy the lines above into the chat and I will read them.

:end
echo.
pause
exit /b %CODE%
