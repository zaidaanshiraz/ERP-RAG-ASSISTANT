# ERP RAG Assistant (Hybrid LLM: Ollama + Groq) — Complete Setup Guide

A Retrieval-Augmented Generation (RAG) system for ERP PDF documentation with source-cited Q&A, runtime LLM mode switching, and an optional feedback loop.

## 📋 Table of Contents
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation Guide](#-installation-guide)
  - [Step 1: Install Python](#step-1-install-python)
  - [Step 2: Install Ollama (Local Mode)](#step-2-install-ollama-local-mode)
  - [Step 3: Get the Project](#step-3-get-the-project)
  - [Step 4: Create Virtual Environment](#step-4-create-virtual-environment)
  - [Step 5: Install Dependencies](#step-5-install-dependencies)
  - [Step 6: Configure Environment (.env)](#step-6-configure-environment-env)
- [Usage Guide](#-usage-guide)
  - [Starting the Server](#starting-the-server)
  - [Accessing the UI](#accessing-the-ui)
  - [Ingesting Documents](#ingesting-documents)
  - [LLM Mode Switching](#llm-mode-switching)
- [Advanced Features](#-advanced-features)
- [API Documentation](#-api-documentation)
- [Tests](#-tests)
- [Troubleshooting](#-troubleshooting)
- [Quick Start Summary](#-quick-start-summary)

---

## ✨ Features

### Core Functionality
- **RAG Q&A with citations**: retrieves relevant chunks and appends a final `Sources:` section.
- **Hybrid LLM backends**:
  - **Local**: Ollama (offline/private)
  - **Cloud**: Groq (fast) using `llama-3.1-8b-instant`
- **PDF ingestion**: uploads to `data/pdfs/`, extracts text, chunks, embeds, and persists a FAISS vector store.
- **FastAPI + Web UI**: UI is served at `/ui/app.html`.

### Advanced Features
- **Feedback system**: submit thumbs up/down and export positive examples for fine-tuning.
- **Feedback-aware re-ranking**: combines semantic similarity with historical feedback.
- **Finance-domain specialization**: detects finance topics and provides specialized instructions.
- **Batch Q&A**: answer multiple questions in one request.

---

## 📁 Project Structure

```
erp-rag-mistral/
  app/
    api.py                    # FastAPI backend + serves UI at /ui

  src/
    config.py                 # CPU/GPU selection (USE_GPU)
    parameters.py             # .env loading + tunables (LLM_MODE, TOP_K, etc.)
    rag.py                    # RAG orchestration + mode switching
    vectorstore.py            # FAISS store build/load + embeddings
    ingest.py                 # PDF ingestion pipeline
    ollama_client.py          # Local LLM client
    groq_client.py            # Cloud LLM client
    feedback.py               # Feedback store + analytics + export
    finance_domain.py         # Finance domain detection + prompts

  ui/
    app.html                  # Frontend
    assets/
      app.js                  # UI logic (mode toggle, upload, query)
      styles.css              # UI styling

  requirements.txt            # Python dependencies
  .env.example                # Environment variables template
  .gitignore                  # Git ignore rules
  README.md                   # This file
  DESIGN_DOCUMENT.md          # Technical design and architecture
  ingest.bat                  # Windows batch file for document ingestion
  start_server.bat            # Windows batch file for server startup
  validate_syntax.py          # Code syntax validation
  test_hybrid_llm.py          # Hybrid LLM system tests
  test_llm_mode_toggle.py     # LLM mode switching tests

  data/                       # (generated at runtime, in .gitignore)
    pdfs/                     # Uploaded PDFs
    processed_chunks/         # Chunk JSON
    vectorstore/              # FAISS index + metadata
    feedback/                 # Feedback JSON + fine-tuning export
```

**Note:** The `data/` directory is generated at runtime and is excluded from Git via `.gitignore`.

---

## 🔧 Prerequisites

1. Windows 10/11 (Linux/macOS should work with minor command changes)
2. Python 3.10+ recommended
3. RAM: 8GB+ (more helps with embeddings)
4. Disk: enough space for PDFs + vectorstore
5. Optional:
   - **Local mode**: Ollama installed and running: https://ollama.com
   - **Cloud mode**: Groq API key: https://console.groq.com/keys

---

## 📦 Installation Guide

### Step 1: Install Python

1. Download Python 3.10+ from https://www.python.org/downloads/
2. During install, enable **Add Python to PATH**.

Verify:

```cmd
python --version
```

### Step 2: Install Ollama (Local Mode)

1. Install Ollama for Windows: https://ollama.com/download
2. Verify it runs:

```powershell
ollama list
```

Pull the default local model:

```powershell
ollama pull qwen2.5:3b-instruct-q4_K_M
```

### Step 3: Get the Project

If you already have the folder, skip.

```cmd
cd "E:\Python Projects"
git clone <your-repo-url> erp-rag-mistral
cd erp-rag-mistral
```

### Step 4: Create Virtual Environment

```powershell
cd "E:\Python Projects\erp-rag-mistral"
python -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Step 5: Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 6: Configure Environment (.env)

Copy the example:

```powershell
Copy-Item .env.example .env
```

Edit `.env` (repo root). Common settings:

- Cloud (Groq):
  - `LLM_MODE=cloud`
  - `GROQ_API_KEY=...`
- Local (Ollama):
  - `LLM_MODE=local`

Device selection:

- `USE_GPU=false` (default)
- `USE_GPU=true` (requires CUDA-capable PyTorch)
- `USE_GPU=auto` (use GPU if available)

Note: the app loads the repo-root `.env` and uses `override=True` so `.env` takes precedence over an existing shell variable.

---

## 🚀 Usage Guide

### Starting the Server

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

### Accessing the UI

- UI: `http://localhost:8000/ui/app.html`
- API docs (Swagger): `http://localhost:8000/docs`

### Ingesting Documents

Option A (recommended): upload PDFs from the UI.

Option B: ingest from disk.

1) Put PDFs in `data/pdfs/`
2) Run:

```powershell
.\.venv\Scripts\python.exe src\ingest.py
```

Outputs:

- `data/processed_chunks/` (chunk JSON)
- `data/vectorstore/` (FAISS index + metadata)

### LLM Mode Switching

- In the UI: use the toggle in the header.
- Via API:

```bash
curl http://localhost:8000/api/llm/mode

curl -X POST http://localhost:8000/api/llm/mode \
  -H "Content-Type: application/json" \
  -d "{\"mode\":\"cloud\"}"
```

---

## 🎯 Advanced Features

### Feedback System

- Submit feedback:

```bash
curl -X POST http://localhost:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is ERP?",
    "answer": "...",
    "sources": [],
    "rating": "positive",
    "comment": "Helpful"
  }'
```

- Analytics:

```bash
curl http://localhost:8000/api/feedback/analytics
```

- Export fine-tuning data:

```bash
curl -X POST http://localhost:8000/api/feedback/export
```

### Finance Domain Detection

```bash
curl "http://127.0.0.1:8000/api/finance/domain?query=How%20to%20post%20a%20journal%20entry"
```

---

## 📚 API Documentation

Swagger UI:

- `http://localhost:8000/docs`

Common endpoints:

- `POST /api/query` (RAG Q&A)
- `POST /api/search` (semantic search)
- `POST /api/batch-query` (batch answers)
- `POST /api/upload` (upload PDF + auto-ingest)
- `POST /api/reload` (reload pipeline from disk)
- `POST /api/feedback` / `GET /api/feedback/analytics` / `POST /api/feedback/export`
- `GET /api/finance/domain`
- `GET /health` / `GET /info`

---

## ✅ Tests

```powershell
.\.venv\Scripts\python.exe validate_syntax.py
.\.venv\Scripts\python.exe test_hybrid_llm.py
```

If the server is running, you can also test the API toggle:

```powershell
.\.venv\Scripts\python.exe test_llm_mode_toggle.py
```

---

## 🐛 Troubleshooting

- `Invalid Groq API key (401)`: confirm `GROQ_API_KEY` in `.env` and that you don't have an older shell `GROQ_API_KEY` overriding it.
- `Cannot connect to Ollama`: start Ollama with `ollama serve` and confirm the model exists with `ollama list`.
- `Index not built`: upload a PDF via the UI or run `src/ingest.py`.
- Slow CPU responses: tune `src/parameters.py` (e.g., `TOP_K_RETRIEVAL`, `MAX_TOKENS`).

---

## 🎉 Quick Start Summary

### Option 1: Using Batch Files (Easiest - Windows)

Simply double-click these files from Windows Explorer:

1. **`ingest.bat`** - Process PDFs and build vector store
   - Just double-click to ingest documents from `data/pdfs/`

2. **`start_server.bat`** - Start server and open UI
   - Just double-click to start the app
   - Server starts on `http://localhost:8000`
   - Browser opens automatically to `http://localhost:8000/ui/app.html`

### Option 2: Manual Command Line

**PowerShell:**
```powershell
cd "E:\Python Projects\erp-rag-mistral"
.\.venv\Scripts\Activate.ps1
python src\ingest.py
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

**CMD:**
```cmd
cd "E:\Python Projects\erp-rag-mistral"
.venv\Scripts\activate
python -m uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Then open:
- `http://localhost:8000/ui/app.html`

---

## 👤 Author & Attribution

**Author:** Zaidaan Shiraz  
**LinkedIn:** https://www.linkedin.com/in/zaidaanshiraz/  
**GitHub:** [erp-rag-mistral](https://github.com/zaidaanshiraz/erp-rag-mistral)

---

## 📄 License

MIT License - See LICENSE file for details

---

## 📊 Document Information

**Project Version:** 1.0.0  
**Document Version:** 1.0  
**Last Updated:** December 17, 2025  
**Status:** Production Ready  

For technical architecture details, design decisions, and future enhancements, see [DESIGN_DOCUMENT.md](DESIGN_DOCUMENT.md).
