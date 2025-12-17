@echo off
REM ============================================================================
REM ERP RAG Assistant - Start Server Script
REM ============================================================================
REM This batch file starts the FastAPI server and opens the UI:
REM 1. Activate virtual environment
REM 2. Start FastAPI server (uvicorn)
REM 3. Open browser to localhost UI
REM ============================================================================

setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo ============================================================================
echo ERP RAG Assistant - Start Server
echo ============================================================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found at .venv\Scripts\activate.bat
    echo Please run: python -m venv .venv
    echo Then: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo        ✓ Virtual environment activated
echo.

REM Check if .env exists
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and configure it first
    pause
    exit /b 1
)

REM Start uvicorn server
echo [2/3] Starting FastAPI server on http://localhost:8000...
echo        (Press Ctrl+C to stop the server)
echo.

REM Open browser in background (with a small delay for server startup)
echo [3/3] Opening browser in 3 seconds...
timeout /t 3 /nobreak
start http://localhost:8000/ui/app.html

echo.
echo ============================================================================
echo Server is running! Browser opened to http://localhost:8000/ui/app.html
echo ============================================================================
echo.

REM Start uvicorn server (this will block until Ctrl+C)
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload

REM Cleanup on exit
echo.
echo ============================================================================
echo Server stopped.
echo Type 'deactivate' to exit the virtual environment.
echo ============================================================================
echo.

pause
