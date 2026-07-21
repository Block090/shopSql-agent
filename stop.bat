@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   Shopkeeper-Agent Stop
echo ============================================================
echo.
echo [1/2] Stopping Docker containers...
docker compose -f docker/docker-compose.yaml down

echo.
echo [2/2] Manually close the backend/frontend windows
echo       (titled shopkeeper-backend / shopkeeper-frontend).
echo.
echo Docker stopped. Done.
echo.
pause
