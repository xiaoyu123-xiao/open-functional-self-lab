@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 发布 open-functional-self-lab

echo ==========================================
echo   open-functional-self-lab  一键发布
echo   等价于 docs/publish.md 的第 0 + 3 步
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 python。请先安装 Python 3.10 以上版本。
    echo        安装时记得勾选 "Add python.exe to PATH"。
    pause
    exit /b 1
)

where git >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 git。请先安装 Git for Windows。
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\publish.ps1" %*
set CODE=%errorlevel%
echo.
if not "%CODE%"=="0" (
    echo [未完成] 退出码 %CODE%。把上面的红字发给我，我帮你看。
) else (
    echo [完成] 已推送到 GitHub。
)
pause
exit /b %CODE%
