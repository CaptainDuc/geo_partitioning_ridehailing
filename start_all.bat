@echo off
title Start All Shards and Gateway
echo.
echo [1/3] Dang khoi dong Shard EU-West (Port 5001)...
start cmd /k "python shards/eu_west/app.py"

echo [2/3] Dang khoi dong Shard EU-North (Port 5002)...
start cmd /k "python shards/eu_north/app.py"

echo [3/3] Dang khoi dong API Gateway (Port 5000)...
start cmd /k "python gateway/app.py"

echo.
echo ======================================================
echo DA KHOI DONG THANH CONG!
echo Vui long truy cap: http://localhost:5000/game
echo ======================================================
echo.
pause
