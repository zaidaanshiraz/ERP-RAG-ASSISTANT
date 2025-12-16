"""
FastAPI REST API for RAG system.

Exposes Q&A, document search, and system info endpoints.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import logging
import shutil
import subprocess

from src.rag import RAGPipeline
from src.vectorstore import VectorStore
from src.ollama_client import OllamaClient
from src.feedback import FeedbackManager
from src.finance_domain import get_finance_instruction, identify_finance_domain

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="ERP RAG System",
    description="Retrieval-Augmented Generation for ERP Q&A",
    version="1.0.0"
)

# Mount static files for UI
ui_path = Path(__file__).parent.parent / "ui"
app.mount("/ui", StaticFiles(directory=str(ui_path)), name="ui")

# Add CORS middleware for web integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize pipeline on startup
rag_pipeline: Optional[RAGPipeline] = None
feedback_manager: Optional[FeedbackManager] = None


@app.on_event("startup")
async def startup_event():
    """Initialize RAG pipeline on startup."""
    global rag_pipeline, feedback_manager
    try:
        logger.info("Initializing RAG pipeline...")
        rag_pipeline = RAGPipeline(top_k=5)
        feedback_manager = FeedbackManager()
        logger.info("RAG pipeline and feedback system ready")
    except Exception as e:
        logger.error(f"Failed to initialize RAG pipeline: {e}")
        raise


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Q&A query request."""
    query: str
    top_k: Optional[int] = 5


class SourceDocument(BaseModel):
    """Retrieved source document."""
    document_name: str
    excerpt: str
    relevance_score: float
    chunk_ids: List[int]


class QueryResponse(BaseModel):
    """Q&A response with citations."""
    answer: str
    sources: List[SourceDocument]
    num_sources: int


class SearchRequest(BaseModel):
    """Document search request."""
    query: str
    top_k: Optional[int] = 5


class SearchResult(BaseModel):
    """Search result."""
    text: str
    source_file: str
    chunk_id: int
    score: float


class SearchResponse(BaseModel):
    """Search response."""
    results: List[SearchResult]
    query: str
    num_results: int


class SystemInfo(BaseModel):
    """System information."""
    status: str
    total_chunks: int
    embedding_model: str
    llm_model: str


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Redirect to UI."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui/app.html")


@app.get("/health")
async def health_check():
    """Check system health."""
    return {
        "status": "healthy" if rag_pipeline else "initializing",
        "ready": rag_pipeline is not None
    }


@app.get("/info", response_model=SystemInfo)
async def get_info():
    """Get system information."""
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="System initializing")
    
    return SystemInfo(
        status="ready",
        total_chunks=len(rag_pipeline.vectorstore.chunks),
        embedding_model=rag_pipeline.vectorstore.model_name,
        llm_model=rag_pipeline.llm.model
    )


# ============================================================================
# Q&A Endpoints
# ============================================================================

@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Answer a question with citations.
    
    The system retrieves relevant documents and uses an LLM to generate
    an answer with proper source attribution.
    """
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="System initializing")
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        logger.info(f"Query: {request.query}")
        response = rag_pipeline.answer(
            query=request.query,
            return_sources=True
        )
        
        return QueryResponse(
            answer=response["answer"],
            sources=[SourceDocument(**source) for source in response["sources"]],
            num_sources=response["num_sources"]
        )
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Search Endpoints
# ============================================================================

@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search documents semantically (without LLM generation).
    
    Returns the most relevant document chunks for a query based on
    semantic similarity.
    """
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="System initializing")
    
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        logger.info(f"Search: {request.query}")
        retrieved = rag_pipeline.retrieve(request.query)
        
        results = [
            SearchResult(
                text=chunk["text"],
                source_file=chunk["source_file"],
                chunk_id=chunk["chunk_id"],
                score=score
            )
            for chunk, score in retrieved[:request.top_k]
        ]
        
        return SearchResponse(
            results=results,
            query=request.query,
            num_results=len(results)
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Batch Endpoints
# ============================================================================

@app.post("/api/batch-query")
async def batch_query(queries: List[str]):
    """
    Answer multiple questions in batch.
    
    Returns answers for multiple queries at once.
    """
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="System initializing")
    
    if not queries or any(not q.strip() for q in queries):
        raise HTTPException(status_code=400, detail="All queries must be non-empty")
    
    try:
        logger.info(f"Batch query: {len(queries)} questions")
        responses = []
        
        for query in queries:
            response = rag_pipeline.answer(query=query, return_sources=False)
            responses.append({
                "query": query,
                "answer": response["answer"]
            })
        
        return {
            "responses": responses,
            "total": len(responses)
        }
    except Exception as e:
        logger.error(f"Batch query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Feedback Endpoints
# ============================================================================

class FeedbackRequest(BaseModel):
    """User feedback request."""
    query: str
    answer: str
    sources: List[dict]
    rating: str  # 'positive' or 'negative'
    comment: Optional[str] = None
    user_id: Optional[str] = None


@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback for answer quality.
    
    Enables learning from user satisfaction to improve future answers.
    """
    if not feedback_manager:
        raise HTTPException(status_code=503, detail="Feedback system not initialized")
    
    if request.rating not in ['positive', 'negative']:
        raise HTTPException(status_code=400, detail="Rating must be 'positive' or 'negative'")
    
    try:
        # Ensure sources is a list
        sources = request.sources if request.sources else []
        
        feedback_entry = feedback_manager.add_feedback(
            query=request.query,
            answer=request.answer,
            sources=sources,
            rating=request.rating,
            comment=request.comment,
            user_id=request.user_id
        )
        
        logger.info(f"Feedback submitted: {request.rating} | Query: {request.query[:50]}...")
        
        return {
            "status": "success",
            "feedback_id": feedback_entry["feedback_id"],
            "message": "Thank you for your feedback!"
        }
    except Exception as e:
        logger.error(f"Feedback submission error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Feedback error: {str(e)}")


@app.get("/api/feedback/analytics")
async def get_feedback_analytics():
    """
    Get feedback analytics dashboard data.
    
    Returns satisfaction rate, top/bottom documents, recent comments.
    """
    if not feedback_manager:
        raise HTTPException(status_code=503, detail="Feedback system not initialized")
    
    try:
        analytics = feedback_manager.get_analytics()
        return analytics
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feedback/export")
async def export_feedback_data():
    """
    Export positive feedback as training data for fine-tuning.
    
    Returns count of exported examples.
    """
    if not feedback_manager:
        raise HTTPException(status_code=503, detail="Feedback system not initialized")
    
    try:
        count = feedback_manager.export_for_finetuning()
        return {
            "status": "success",
            "exported_examples": count,
            "file": "data/feedback/finetuning_data.jsonl"
        }
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Finance Domain Endpoint
# ============================================================================

@app.get("/api/finance/domain")
async def identify_query_domain(query: str):
    """
    Identify the finance domain of a query.
    
    Returns domain category (GL, AP, AR, etc.) for finance-specific routing.
    """
    try:
        domain = identify_finance_domain(query)
        return {
            "query": query,
            "domain": domain,
            "specialized_instruction_available": domain != "general_finance"
        }
    except Exception as e:
        logger.error(f"Domain identification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Document Upload & Processing Pipeline
# ============================================================================

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF document and immediately process it.
    
    Auto-runs ingest.py to extract text, chunk, embed, and index in vectorstore.
    Returns status and processing details.
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Create upload directory if not exists
        upload_dir = Path("data/pdfs")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"File uploaded: {file.filename}")
        
        # AUTOMATICALLY run ingest.py to process the document
        logger.info(f"Auto-processing document: {file.filename}")
        import sys
        result = subprocess.run(
            [sys.executable, "src/ingest.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode != 0:
            logger.error(f"Ingestion stderr: {result.stderr}")
            raise Exception(f"Document processing failed: {result.stderr}")
        
        # Count chunks created
        import json
        chunks_file = Path("data/processed_chunks/chunks.json")
        total_chunks = 0
        if chunks_file.exists():
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
                total_chunks = len(chunks)
        
        logger.info(f"Document processed and vectorized: {total_chunks} chunks created")
        
        return {
            "status": "success",
            "filename": file.filename,
            "path": str(file_path),
            "message": f"File '{file.filename}' uploaded and processed successfully",
            "chunks_created": total_chunks,
            "converted_markdown": "converted_docs/",
            "vectorstore_ready": True
        }
    
    except Exception as e:
        logger.error(f"Upload/processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/process-document")
async def process_document(request: dict):
    """
    Process uploaded document with ingest.py (extract text and chunk).
    
    Expects: {"filename": "document.pdf"}
    """
    try:
        filename = request.get("filename")
        if not filename:
            raise HTTPException(status_code=400, detail="Filename required")
        
        # Run ingest.py using the current Python interpreter
        logger.info(f"Processing document: {filename}")
        import sys
        result = subprocess.run(
            [sys.executable, "src/ingest.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        
        if result.returncode != 0:
            logger.error(f"Ingestion stderr: {result.stderr}")
            raise Exception(f"Ingestion failed: {result.stderr}")
        
        logger.info(f"Document processed: {filename}")
        
        return {
            "status": "success",
            "message": "Document processed and chunked",
            "output": result.stdout
        }
    
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-embeddings")
async def generate_embeddings():
    """
    Verify embeddings are generated for all chunks.
    
    Note: Embeddings are automatically created during document ingestion in ingest.py.
    This endpoint verifies the FAISS index was built successfully.
    """
    try:
        logger.info("Verifying embeddings...")
        
        # Count chunks
        import json
        chunks_file = Path("data/chunks.json")
        if chunks_file.exists():
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
                total_chunks = len(chunks)
        else:
            total_chunks = 0
        
        # Verify FAISS index exists
        index_file = Path("data/faiss_index.bin")
        has_index = index_file.exists()
        
        logger.info(f"Verified {total_chunks} chunks with {'FAISS index' if has_index else 'no index (pending document ingestion)'}")
        
        return {
            "status": "success",
            "message": "Embeddings verified (auto-generated during document ingestion)",
            "total_chunks": total_chunks,
            "has_faiss_index": has_index
        }
    
    except Exception as e:
        logger.error(f"Embedding verification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reload")
async def reload_system():
    """
    Reload RAG pipeline with new embeddings.
    
    Forces vectorstore to reload from disk.
    """
    global rag_pipeline
    
    try:
        logger.info("Reloading RAG system...")
        
        # Reinitialize RAG pipeline
        rag_pipeline = RAGPipeline(top_k=5)
        
        logger.info("RAG system reloaded successfully")
        
        return {
            "status": "success",
            "message": "RAG system reloaded with new documents"
        }
    
    except Exception as e:
        logger.error(f"Reload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Static Content
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API documentation."""
    return {
        "message": "ERP RAG System API",
        "docs": "/docs",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "info": "GET /info",
            "query": "POST /api/query",
            "search": "POST /api/search",
            "batch_query": "POST /api/batch-query",
            "feedback": "POST /api/feedback",
            "analytics": "GET /api/feedback/analytics",
            "export_feedback": "POST /api/feedback/export",
            "identify_domain": "GET /api/finance/domain",
            "upload": "POST /api/upload",
            "process_document": "POST /api/process-document",
            "generate_embeddings": "POST /api/generate-embeddings",
            "reload_system": "POST /api/reload"
        }
    }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("ERP RAG System - FastAPI Server")
    print("="*60)
    print("\nStarting server on http://localhost:8000")
    print("Documentation: http://localhost:8000/docs\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
