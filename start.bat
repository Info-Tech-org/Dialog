@echo off
setlocal
rem Simplified launcher with robust start syntax to avoid path/encoding issues

rem Always work from script directory
cd /d "%~dp0"
set "ROOT=%CD%"
set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
echo [INFO] Working directory: %ROOT%
echo.

rem Sanity checks
if not exist "%BACKEND_DIR%" (
  echo [ERROR] Missing backend directory. Please run in the project root.
  pause
  exit /b 1
)
if not exist "%FRONTEND_DIR%" (
  echo [ERROR] Missing frontend directory. Please run in the project root.
  pause
  exit /b 1
)

rem Prepare data folders
if not exist "%BACKEND_DIR%\data" mkdir "%BACKEND_DIR%\data" 2>nul
if not exist "%BACKEND_DIR%\data\audio" mkdir "%BACKEND_DIR%\data\audio" 2>nul
if not exist "%BACKEND_DIR%\data\audio\uploads" mkdir "%BACKEND_DIR%\data\audio\uploads" 2>nul
if not exist "%BACKEND_DIR%\data\audio\processed" mkdir "%BACKEND_DIR%\data\audio\processed" 2>nul

echo [INFO] Starting backend (port 8000)...
start "backend-fastapi" /D "%BACKEND_DIR%" cmd /k "color 0B && echo ==== Backend (FastAPI) ==== && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
if errorlevel 1 (
  echo [ERROR] Failed to start backend window.
  pause
  exit /b 1
)

timeout /t 2 /nobreak > nul

echo [INFO] Starting frontend (port 3000)...
start "frontend-vite" /D "%FRONTEND_DIR%" cmd /k "color 0E && echo ==== Frontend (Vite) ==== && npm run dev"
if errorlevel 1 (
  echo [ERROR] Failed to start frontend window.
  pause
  exit /b 1
)

echo.
echo [DONE] Windows launched:
echo   - backend-fastapi : FastAPI server logs
echo   - frontend-vite   : Vite dev server logs
echo Close those windows to stop services, or run stop.bat if provided.
echo.

pause
endlocal
