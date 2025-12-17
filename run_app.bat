@echo off
REM ============================================================================
REM ERP RAG Assistant - Automated Startup Script
REM ============================================================================
REM This batch file automates the entire app startup process:
REM 1. Activate virtual environment
REM 2. Ingest documents (src/ingest.py)
REM 3. Start FastAPI server (uvicorn)
REM 4. Open browser to UI
REM ============================================================================

setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo ============================================================================
echo ERP RAG Assistant - Startup
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
echo [1/4] Activating virtual environment...
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
    echo WARNING: .env file not found!
    echo Copying from .env.example...
    if exist ".env.example" (
        copy .env.example .env
        echo [!] Created .env - please edit it with your API keys and settings before running again
        pause
        exit /b 1
    ) else (
        echo ERROR: .env.example not found either
        pause
        exit /b 1
    )
)

REM Run ingestion pipeline
echo [2/4] Ingesting documents (this may take a moment)...
python src\ingest.py
if errorlevel 1 (
    echo WARNING: Document ingestion failed or no documents to ingest
    echo You can upload PDFs via the UI later
    echo.
) else (
    echo        ✓ Documents ingested successfully
)
echo.

REM Start uvicorn server
echo [3/4] Starting FastAPI server on http://localhost:8000...
echo        (Press Ctrl+C to stop the server)
echo.

REM Open browser in background (with a small delay for server startup)
echo [4/4] Opening browser...
timeout /t 2 /nobreak
start http://localhost:8000/ui/app.html

REM Start uvicorn server (this will block until Ctrl+C)
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000

REM Cleanup on exit
echo.
echo ============================================================================
echo Server stopped. Virtual environment still active.
echo Type 'deactivate' to exit the virtual environment.
echo ============================================================================
echo.

pause
