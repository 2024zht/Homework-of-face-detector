@echo off
REM ============================================
REM Lab Check-in System Launcher
REM ============================================
echo Starting Lab Check-in System...
echo.

REM 1. Activate conda environment
call conda activate facedetector
if errorlevel 1 (
    echo [ERROR] Cannot activate facedetector environment
    pause
    exit /b 1
)

REM 2. Start the FastAPI server (in background)
echo [1/2] Starting FastAPI server on port 8080...
start "CheckIn-Server" cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --log-level info"
timeout /t 3 /nobreak >nul

REM 3. Start cpolar (adjust path if needed)
echo [2/2] Starting cpolar tunnel...
echo.
echo   *** 请手动运行: .\cpolar http 8080  ***
echo.
echo Local access: http://localhost:8080
echo Admin: http://localhost:8080/login.html (admin / admin123)
echo.
echo Press any key to stop server...
pause >nul
taskkill /fi "WINDOWTITLE eq CheckIn-Server" >nul 2>&1
