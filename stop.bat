@echo off
chcp 65001 > nul
color 0C
title 停止服务

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║          家庭情绪交互系统 - 停止服务                      ║
echo ║      Family Emotion Interaction System                    ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo [1/3] 停止后端服务 (端口 8000)...
taskkill /FI "WINDOWTITLE eq 🔧 后端服务*" /F >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a > nul 2>&1
)
echo [✓] 后端服务已停止

echo.
echo [2/3] 停止前端服务 (端口 3000)...
taskkill /FI "WINDOWTITLE eq 🎨 前端服务*" /F >nul 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a > nul 2>&1
)
echo [✓] 前端服务已停止

echo.
echo [3/3] 清理进程...
taskkill /FI "WINDOWTITLE eq 后端服务*" /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq 前端服务*" /F >nul 2>nul
echo [✓] 清理完成

echo.
echo ════════════════════════════════════════════════════════════
echo.
echo   ✓ 所有服务已停止
echo.
echo ════════════════════════════════════════════════════════════
echo.
pause
