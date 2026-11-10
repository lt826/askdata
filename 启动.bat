@echo off
title AskData Launcher
cd /d %~dp0

echo ================================================================
echo   AskData one-click launcher
echo   (Database is a local DuckDB file - no Docker needed)
echo ================================================================
echo.

echo [1/5] Checking .venv ...
if exist ".venv\Scripts\python.exe" (
    echo   [OK] venv ready
) else (
    echo   [!] venv NOT found. Run:  uv sync
    pause
    exit /b 1
)

echo [2/5] Checking database ...
if exist "data\sales.duckdb" (
    echo   [OK] sales.duckdb found
) else (
    echo   [!] Database NOT found. Build it first:
    echo       .venv\Scripts\python.exe scripts\gen_dataset.py
    echo       .venv\Scripts\python.exe scripts\build_db.py
    echo       Then run this launcher again.
    pause
    exit /b 1
)

echo [3/5] Checking .env ...
if exist ".env" (
    echo   [OK] .env found
) else (
    echo   [!] .env NOT found - copy .env.example and fill ZHIPU_API_KEY
    pause
    exit /b 1
)

echo [4/5] Starting backend FastAPI  :8001 ...
start "AskData-Backend" cmd /k ".venv\Scripts\python.exe scripts\run_server.py"

echo [5/5] Starting frontend Vite    :5175 ...
start "AskData-Frontend" cmd /k "cd web && npm run dev -- --port 5175"

echo.
echo Waiting for services, then opening browser...
timeout /t 8 >nul
start http://localhost:5175
echo.
echo Done. To STOP: close the [AskData-Backend] / [AskData-Frontend] windows.
pause
