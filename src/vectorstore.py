"""
Vector embeddings and semantic search with FAISS.

Uses sentence-transformers for embeddings and FAISS for similarity search.
"""

import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from src.config import config


class VectorStore:
    """Manage embeddings and semantic search with FAISS."""
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        store_dir: str = "data/vectorstore"
    ):
        """
        Initialize vector store.
        
        Args:
            model_name: Sentence-transformer model (default: small, fast)
            store_dir: Directory to save index and metadata
        """
        self.model_name = model_name
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[VectorStore] Loading model: {model_name}...")
        self.model = SentenceTransformer(model_name, device=config.device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        print(f"[VectorStore] Embedding dimension: {self.embedding_dim}")
        print(f"[VectorStore] Device: {config.device}")
        
        # Placeholders for index and metadata
        self.index = None
        self.chunks = []
    
    def embed_chunks(self, chunks: List[Dict]) -> np.ndarray:
        """
        Create embeddings for all chunks.
        
        Args:
            chunks: List of chunk dicts with 'text' field
        
        Returns:
            Numpy array of embeddings
        """
        texts = [chunk["text"] for chunk in chunks]
        
        print(f"[VectorStore] Creating embeddings for {len(texts)} chunks...")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        
        return np.array(embeddings).astype('float32')
    
    def build_index(self, embeddings: np.ndarray) -> None:
        """
        Build FAISS index from embeddings.
        
        Args:
            embeddings: Numpy array of embeddings
        """
        print(f"[VectorStore] Building FAISS index...")
        
        # Create index: simple flat index with L2 distance
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        self.index.add(embeddings)
        
        print(f"[VectorStore] Index built with {self.index.ntotal} vectors")
    
    def ingest_chunks(self, chunks: List[Dict]) -> None:
        """
        Ingest chunks and build index.
        
        Args:
            chunks: List of chunk dicts from ingest.py
        """
        # Store chunks for metadata lookup
        self.chunks = chunks
        
        # Create embeddings
        embeddings = self.embed_chunks(chunks)
        
        # Build FAISS index
        self.build_index(embeddings)
        
        # Save index and metadata
        self.save()
    
    def search(self, query: str, k: int = 5) -> List[Tuple[Dict, float]]:
        """
        Semantic search for query.
        
        Args:
            query: Search query
            k: Number of top results to return
        
        Returns:
            List of (chunk, score) tuples sorted by relevance
        
        Raises:
            RuntimeError: If index not built
        """
        if self.index is None:
            raise RuntimeError("Index not built. Call ingest_chunks() first.")
        
        # Embed query
        query_embedding = self.model.encode([query])[0].astype('float32')
        
        # Search index
        distances, indices = self.index.search(
            np.array([query_embedding]),
            k=min(k, self.index.ntotal)
        )
        
        # Return results with scores
        results = []
        for idx, distance in zip(indices[0], distances[0]):
            if idx >= 0:  # Valid result
                chunk = self.chunks[int(idx)]
                # Convert L2 distance to similarity (inverse)
                similarity = 1 / (1 + distance)
                results.append((chunk, float(similarity)))
        
        return results
    
    def save(self) -> None:
        """Save index and metadata to disk."""
        if self.index is None:
            raise RuntimeError("No index to save")
        
        # Save FAISS index
        index_path = self.store_dir / "faiss.index"
        faiss.write_index(self.index, str(index_path))
        print(f"[VectorStore] Saved index: {index_path}")
        
        # Save metadata (chunks)
        metadata_path = self.store_dir / "metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.chunks, f)
        print(f"[VectorStore] Saved metadata: {metadata_path}")
    
    def load(self) -> None:
        """Load index and metadata from disk."""
        index_path = self.store_dir / "faiss.index"
        metadata_path = self.store_dir / "metadata.pkl"
        
        if not index_path.exists() or not metadata_path.exists():
            raise RuntimeError(
                f"Index or metadata not found in {self.store_dir}\n"
                f"Run ingest_chunks() first to build the index."
            )
        
        # Load FAISS index
        self.index = faiss.read_index(str(index_path))
        print(f"[VectorStore] Loaded index with {self.index.ntotal} vectors")
        
        # Load metadata
        with open(metadata_path, 'rb') as f:
            self.chunks = pickle.load(f)
        print(f"[VectorStore] Loaded metadata for {len(self.chunks)} chunks")


def main():
    """Build vector store from processed chunks."""
    # Load chunks from ingest output
    chunks_path = Path("data/processed_chunks/chunks.json")
    if not chunks_path.exists():
        raise RuntimeError(
            f"Chunks file not found: {chunks_path}\n"
            f"Run: python -m src.ingest"
        )
    
    print(f"[Pipeline] Loading chunks from {chunks_path}...")
    with open(chunks_path) as f:
        chunks = json.load(f)
    print(f"[Pipeline] Loaded {len(chunks)} chunks\n")
    
    # Create and ingest into vector store
    store = VectorStore()
    store.ingest_chunks(chunks)
    
    # Test search
    print("\n" + "="*60)
    print("TESTING SEARCH")
    print("="*60)
    
    test_queries = [
        "What is ERP?",
        "How to implement manufacturing?",
        "What are the benefits?"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        results = store.search(query, k=3)
        for i, (chunk, score) in enumerate(results, 1):
            print(f"  {i}. Score: {score:.3f} | {chunk['source_file']}")
            print(f"     {chunk['text'][:100]}...")


if __name__ == "__main__":
    main()
