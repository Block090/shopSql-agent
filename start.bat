@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   Shopkeeper-Agent Start (Docker + Backend + Frontend)
echo ============================================================
echo.

echo [1/3] Starting Docker containers...
docker compose -f docker/docker-compose.yaml up -d
if errorlevel 1 (
  echo.
  echo [X] Docker failed. Open Docker Desktop first, then retry.
  echo.
  pause
  exit /b 1
)

echo [2/3] Waiting for containers to init (8s)...
timeout /t 8 /nobreak >nul

echo [3/3] Launching backend and frontend in new windows...

REM Backend: UTF-8 env required, otherwise console emoji output crashes it
start "shopkeeper-backend" cmd /k "chcp 65001 >nul& set PYTHONUTF8=1& set PYTHONIOENCODING=utf-8& uv run fastapi dev main.py"

REM Frontend: Vite dev server, /api auto-proxies to backend :8000
start "shopkeeper-frontend" cmd /k "cd frontend && pnpm dev"

echo.
echo ============================================================
echo   Started. Keep the two new windows open (do not close).
echo.
echo   App page:   http://localhost:5173
echo   API docs:   http://127.0.0.1:8000/docs
echo.
echo   To stop: close those two windows, then run stop.bat
echo ============================================================
echo.
echo Wait ~10s for backend, then press any key to open browser...
pause >nul
start "" http://localhost:5173
