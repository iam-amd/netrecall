@echo off
title NetRecall Demo Launcher
color 0A

echo.
echo  ==========================================
echo   NetRecall -- ISP Intelligence Demo
echo  ==========================================
echo.

REM -- Move to script directory so relative paths work
cd /d "%~dp0"

REM -- Check .env exists
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Copy .env.example to .env and fill in your keys.
    echo.
    pause
    exit /b 1
)

echo [1/3] Starting Webhook Server on port 5050...
start "NetRecall Webhook" cmd /k "python -m uvicorn webhook_server:app --host 0.0.0.0 --port 5050"

timeout /t 2 /nobreak >nul

echo [2/3] Starting Streamlit UI on port 8504...
start "NetRecall UI" cmd /k "python -m streamlit run app.py --server.port 8504 --server.headless false"

timeout /t 3 /nobreak >nul

echo [3/3] Opening browser...
start "" "http://localhost:8504"

echo.
echo  ==========================================
echo   Both servers are running!
echo.
echo   UI:       http://localhost:8504
echo   Webhook:  http://localhost:5050/health
echo.
echo   Next step: run ngrok in a separate terminal
echo     ngrok http 5050
echo   Then paste the https URL into .env as
echo     WEBHOOK_BASE_URL=https://xxxx.ngrok-free.app
echo   Then set Twilio webhook URLs (see DEMO_GUIDE.md)
echo  ==========================================
echo.
pause
