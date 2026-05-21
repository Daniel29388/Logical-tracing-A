@echo off
setlocal EnableExtensions

cd /d "%~dp0"

if /I "%~1"=="--check" (
    echo start_web.bat is ready.
    exit /b 0
)

set "PYTHON_EXE=C:\Users\DFG\.conda\envs\py310\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

set "PYTHONPATH=%CD%;%PYTHONPATH%"
set "TRADINGAGENTS_RESULTS_DIR=%CD%\.tradingagents\logs"
set "TRADINGAGENTS_CACHE_DIR=%CD%\.tradingagents\cache"
if not defined TRADINGAGENTS_USE_TDX_FIRST set "TRADINGAGENTS_USE_TDX_FIRST=1"
if not defined TRADINGAGENTS_TDX_SERVER set "TRADINGAGENTS_TDX_SERVER=110.41.147.114:7709"
if not defined TRADINGAGENTS_TDX_TIMEOUT set "TRADINGAGENTS_TDX_TIMEOUT=5"
if not defined TRADINGAGENTS_TDX_SOCKET_TIMEOUT set "TRADINGAGENTS_TDX_SOCKET_TIMEOUT=1.2"
if not defined TRADINGAGENTS_TDX_MAX_SERVERS set "TRADINGAGENTS_TDX_MAX_SERVERS=12"

if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)

echo.
echo [TradingAgents AStock] Starting web frontend...
echo Project: %CD%
echo Python:  %PYTHON_EXE%
echo.

"%PYTHON_EXE%" -c "import importlib.util, sys; mods=['streamlit','stockstats','mootdx','yfinance','parsel']; sys.exit(0 if all(importlib.util.find_spec(m) for m in mods) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Missing web/data dependencies. Installing with Tsinghua mirror now...
    "%PYTHON_EXE%" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120 --retries 5 streamlit fpdf2 stockstats mootdx yfinance parsel requests rich tqdm pytz
    if errorlevel 1 (
        echo.
        echo Failed to install dependencies.
        echo You can retry later with:
        echo "%PYTHON_EXE%" -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple streamlit fpdf2 stockstats mootdx yfinance parsel requests rich tqdm pytz
        echo.
        pause
        exit /b 1
    )
)

if not defined DEEPSEEK_API_KEY (
    echo DEEPSEEK_API_KEY is not set.
    echo For permanent use, create a .env file in this folder with:
    echo DEEPSEEK_API_KEY=your_key_here
    echo.
    set /p "DEEPSEEK_API_KEY=Paste DeepSeek key for this run, or press Enter to skip: "
    if not defined DEEPSEEK_API_KEY (
        echo The frontend will still open, but DeepSeek runs need the key.
    )
    echo.
)

echo Opening http://localhost:8501
echo Press Ctrl+C in this window to stop the frontend.
echo.

"%PYTHON_EXE%" -m streamlit run "%CD%\web\app.py" --server.address 127.0.0.1 --server.port 8501

echo.
echo Frontend stopped.
pause
