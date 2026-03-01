@echo off
echo ========================================
echo Starting Family MVP Backend Server
echo ========================================
echo.

REM Activate conda environment
call conda activate familymvp

REM Check if activation was successful
if %errorlevel% neq 0 (
    echo Error: Failed to activate conda environment 'familymvp'
    echo Please create the environment first:
    echo   conda env create -f environment.yml
    pause
    exit /b 1
)

echo Conda environment activated: familymvp
echo.

REM Start the backend server
echo Starting FastAPI server...
python -m backend.main

pause
