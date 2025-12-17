@echo off
REM ============================================================================
REM ERP RAG Assistant - Document Ingestion Script
REM ============================================================================
REM This batch file ingests documents into the vector store:
REM 1. Activate virtual environment
REM 2. Run document ingestion pipeline (src/ingest.py)
REM ============================================================================

setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo.
echo ============================================================================
echo ERP RAG Assistant - Document Ingestion
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
echo [1/2] Activating virtual environment...
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

REM Run ingestion pipeline
echo [2/2] Ingesting documents...
echo        Place your PDF files in: data\pdfs\
echo        Processing will extract text, chunk, and build vector store...
echo.

python src\ingest.py

if errorlevel 1 (
    echo.
    echo ERROR: Document ingestion failed
    pause
    exit /b 1
) else (
    echo.
    echo ============================================================================
    echo ✓ Document ingestion completed successfully!
    echo ============================================================================
    echo.
    echo Vector store location: data\vectorstore\
    echo Processed chunks: data\processed_chunks\chunks.json
    echo.
    echo Next step: Run 'start_server.bat' to start the FastAPI server
    echo.
)

pause
