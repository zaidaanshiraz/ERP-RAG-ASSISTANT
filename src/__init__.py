"""Top-level `src` package.

Keep imports lightweight.

Historically this module eagerly imported heavy dependencies (torch, sentence-transformers, PyMuPDF).
That made even simple imports like `from src import parameters` slow and brittle.

We expose key classes via lazy attribute access for backwards compatibility.
"""

from __future__ import annotations

from typing import Any


__all__ = [
	"OllamaClient",
	"DocumentIngester",
	"TextCleaner",
	"DocumentChunker",
	"VectorStore",
	"RAGPipeline",
]


def __getattr__(name: str) -> Any:
	if name == "OllamaClient":
		from .ollama_client import OllamaClient

		return OllamaClient
	if name in {"DocumentIngester", "TextCleaner", "DocumentChunker"}:
		from .ingest import DocumentIngester, TextCleaner, DocumentChunker

		return {"DocumentIngester": DocumentIngester, "TextCleaner": TextCleaner, "DocumentChunker": DocumentChunker}[name]
	if name == "VectorStore":
		from .vectorstore import VectorStore

		return VectorStore
	if name == "RAGPipeline":
		from .rag import RAGPipeline

		return RAGPipeline
	raise AttributeError(f"module 'src' has no attribute {name!r}")
