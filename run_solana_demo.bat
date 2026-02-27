@echo off
setlocal enabledelayedexpansion

set PY=.venv\Scripts\python.exe
if not exist %PY% (
  echo ERROR: venv python not found at %PY%
  echo Activate venv or create it first.
  exit /b 1
)

REM Usage:
REM   run_solana_demo.bat sol-test usd

set ACCOUNT=%1
if "%ACCOUNT%"=="" set ACCOUNT=sol-test

set CURRENCY=%2
if "%CURRENCY%"=="" set CURRENCY=usd

echo === Solana demo flow ===
echo Account: %ACCOUNT%
echo Currency: %CURRENCY%
echo.

REM Read address + assets from accounts.json (2 lines: address then assets)
set "ADDRESS="
set "ASSETS="

for /f "usebackq delims=" %%L in (`"%PY%" scripts\get_account_meta.py %ACCOUNT%`) do (
  if not defined ADDRESS (
    set "ADDRESS=%%L"
  ) else (
    set "ASSETS=%%L"
  )
)

if "%ADDRESS%"=="" (
  echo ERROR: No address found for account '%ACCOUNT%' in accounts.json
  exit /b 1
)

if "%ASSETS%"=="" (
  echo ERROR: No default_assets found for account '%ACCOUNT%' in accounts.json
  exit /b 1
)

echo Using address: %ADDRESS%
echo Using assets: %ASSETS%
echo.

echo [1/3] Updating balances from Solana RPC...
%PY% run_balances_to_db.py --source solana --account %ACCOUNT% --address %ADDRESS% --no-report
if errorlevel 1 goto :err

echo.
echo [2/3] Updating prices (CoinGecko + Dex fallback)...
%PY% run_prices_to_db.py --assets %ASSETS% --currency %CURRENCY% --dex --quiet
if errorlevel 1 goto :err

echo.
echo [3/3] Wallet report:
%PY% wallet_cli.py --account %ACCOUNT% --currency %CURRENCY%
if errorlevel 1 goto :err

echo.
echo Done.
exit /b 0

:err
echo.
echo ERROR: demo flow failed.
exit /b 1