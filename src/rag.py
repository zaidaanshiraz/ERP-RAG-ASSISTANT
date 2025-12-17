"""
RAG (Retrieval-Augmented Generation) pipeline.

Combines semantic search with LLM generation for question-answering with citations.
Supports hybrid LLM modes: local Ollama or cloud Groq.

SYSTEM PROMPTS:
- System prompts are defined in each LLM client (ollama_client.py and groq_client.py)
- These prompts are automatically used for ALL queries regardless of source
- Web UI queries -> API endpoint -> RAG pipeline -> LLM client with system prompt
- Direct RAG queries -> RAG pipeline -> LLM client with system prompt
- System prompts guide responses to be conversational with proper citations
- Same system prompt is used for both local and cloud LLM modes
"""

import sys
import gc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Tuple, Dict, Union, Optional, TYPE_CHECKING
from src.vectorstore import VectorStore
from src.ollama_client import OllamaClient
from src import parameters


if TYPE_CHECKING:
    from src.groq_client import GroqClient


def create_llm_client(mode: Optional[str] = None):
    """
    Factory function to create appropriate LLM client.
    
    Args:
        mode: LLM mode ("local" or "cloud"). Uses parameters.LLM_MODE if not specified.
    
    Returns:
        OllamaClient or GroqClient instance
    
    Raises:
        ValueError: If mode is invalid
        RuntimeError: If client initialization fails
    """
    mode = mode or parameters.LLM_MODE
    
    if mode.lower() == "local":
        return OllamaClient()
    elif mode.lower() == "cloud":
        from src.groq_client import GroqClient
        return GroqClient()
    else:
        raise ValueError(f"Invalid LLM mode: {mode}. Must be 'local' or 'cloud'")


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for Q&A with citations."""
    
    def __init__(
        self,
        vectorstore: VectorStore = None,
        llm_client: Optional[Union[OllamaClient, "GroqClient"]] = None,
        top_k: int = None,
        llm_mode: Optional[str] = None
    ):
        """
        Initialize RAG pipeline.
        
        Args:
            vectorstore: VectorStore instance (or load from disk)
            llm_client: LLM client instance (OllamaClient or GroqClient, or create based on llm_mode)
            top_k: Number of documents to retrieve for context (uses parameters.TOP_K_RETRIEVAL if not set)
            llm_mode: LLM mode ("local" or "cloud"). If not provided and llm_client is None, uses parameters.LLM_MODE
        """
        self.top_k = top_k if top_k is not None else parameters.TOP_K_RETRIEVAL
        
        # Initialize or load vector store
        if vectorstore is None:
            self.vectorstore = VectorStore()
            self.vectorstore.load()
        else:
            self.vectorstore = vectorstore
        
        # Initialize or create LLM client
        if llm_client is None:
            self.llm = create_llm_client(mode=llm_mode)
        else:
            self.llm = llm_client
        
        # Store current mode for potential switching
        self._current_mode = self._detect_llm_mode(self.llm)

        # In cloud mode, retrieve more context for higher-quality answers.
        if top_k is None and self._current_mode == "cloud":
            self.top_k = max(self.top_k, 5)
    
    def _detect_llm_mode(self, llm_client) -> str:
        """Detect which LLM mode is being used."""
        client_type = type(llm_client).__name__
        if "Ollama" in client_type:
            return "local"
        elif "Groq" in client_type:
            return "cloud"
        return "unknown"
    
    def switch_llm_mode(self, new_mode: str) -> None:
        """
        Switch between local and cloud LLM modes.
        
        Args:
            new_mode: Target mode ("local" or "cloud")
        
        Raises:
            ValueError: If mode is invalid
            RuntimeError: If new client initialization fails
        """
        if new_mode == self._current_mode:
            return  # Already using this mode
        
        self.llm = create_llm_client(mode=new_mode)
        self._current_mode = new_mode
        print(f"[RAG] Switched LLM mode to: {new_mode}")
    
    def retrieve(self, query: str) -> List[Tuple[Dict, float]]:
        """
        Retrieve relevant chunks for query.
        
        Args:
            query: User question
        
        Returns:
            List of (chunk, score) tuples
        """
        return self.vectorstore.search(query, k=self.top_k)
    
    def build_context(self, retrieved_chunks: List[Tuple[Dict, float]]) -> str:
        """
        Build context string from retrieved chunks.
        
        Args:
            retrieved_chunks: Results from retrieve()
        
        Returns:
            Formatted context string
        """
        context_parts = []
        for i, (chunk, score) in enumerate(retrieved_chunks, 1):
            context_parts.append(
                f"[Document {i}, Score: {score:.2f}]\n"
                f"Source: {chunk['source_file']}\n"
                f"Content: {chunk['text']}\n"
            )
        return "\n".join(context_parts)
    
    def build_structured_prompt(self, user_question: str, retrieved_chunks: List[Tuple[Dict, float]]) -> str:
        """
        Build structured prompt for LLM with context tags and ERP-specific instructions.
        
        Args:
            user_question: User's question
            retrieved_chunks: List of (chunk_dict, score) tuples from retrieval
        
        Returns:
            Formatted prompt string with context and instructions
        """
        # Get unique document names for source list
        unique_docs = []
        seen_docs = set()
        for chunk, score in retrieved_chunks:
            doc_name = chunk['source_file']
            if doc_name not in seen_docs:
                unique_docs.append(doc_name)
                seen_docs.add(doc_name)
        
        # Build context section
        context_lines = ["<context>"]
        for i, (chunk, score) in enumerate(retrieved_chunks, 1):
            context_lines.append(f"\n[Document {i}]")
            context_lines.append(f"Source: {chunk['source_file']}")
            context_lines.append(f"Content: {chunk['text']}")
        context_lines.append("\n</context>")
        
        context_block = "\n".join(context_lines)
        
        # Build available sources list for reference
        sources_list = "\n".join([f"- {doc}" for doc in unique_docs])
        
        mode = getattr(self, "_current_mode", "local")

        if mode == "cloud":
            grounding_rule = (
                "Use the provided context as your primary source. If the documents do not explicitly cover the question, "
                "you MAY add clearly-labeled general ERP best-practice guidance (do not invent vendor-specific facts)."
            )
            length_rule = "Target length: ~300–900 words when helpful (avoid one-line answers)."
            insufficiency_rule = (
                "If the context is thin or only partially relevant: briefly state what's missing, ask up to 2 clarifying questions, "
                "and still provide helpful general ERP guidance clearly labeled as general (not claimed to come from the documents)."
            )
        else:
            grounding_rule = "Use only the provided context. Do not add external knowledge."
            length_rule = "Target length: ~150–350 words (concise but complete)."
            insufficiency_rule = (
                "If the context is insufficient to answer confidently, say so and suggest what to look for in the available sources."
            )

        # Clean, mode-aware prompt (avoid stray markdown fences that can truncate output)
        prompt = f"""{context_block}

AVAILABLE SOURCES:
{sources_list}

QUESTION:
{user_question}

INSTRUCTIONS:
- Answer clearly and directly, then add details as needed.
- Structure with short sections and bullet points where appropriate.
- Cite sources naturally in the body (e.g., \"According to [Document Name]...\").
- End with a final section titled \"Sources:\".
    - List only the documents you used.
    - If you used none, write: "Sources: None".
- {grounding_rule}
- {length_rule}

{insufficiency_rule}
"""
        return prompt
    
    def build_prompt(self, query: str, context: str) -> str:
        """
        Build LLM prompt with query and context.
        
        DEPRECATED: Use build_structured_prompt() for better results.
        Kept for backward compatibility.
        
        Args:
            query: User question
            context: Retrieved context
        
        Returns:
            Formatted prompt for LLM
        """
        prompt = f"""You are an ERP system expert answering questions based on provided documents.

CONTEXT:
{context}

QUESTION: {query}

INSTRUCTIONS:
1. Answer based only on the provided context
2. If information is not in context, say "I don't have this information in the knowledge base"
3. Always cite which document(s) you used for your answer
4. Be concise and specific

ANSWER:"""
        return prompt
    
    def answer(self, query: str, return_sources: bool = True) -> Dict:
        """
        Generate answer to question with citations.
        
        Args:
            query: User question
            return_sources: Include source documents in response
        
        Returns:
            Dict with:
                - answer: Generated response text
                - sources: Retrieved documents (if return_sources=True)
                - scores: Relevance scores
        """
        try:
            # Retrieve relevant documents
            retrieved = self.retrieve(query)

            # Deduplicate and merge similar sources (used for UI + optional LLM citation formatting)
            deduplicated_sources = self._deduplicate_sources(retrieved)
            top_sources = deduplicated_sources[:3]
            
            # Build structured prompt with context tags
            prompt = self.build_structured_prompt(query, retrieved)
            
            # Generate answer
            answer_text = self.llm.generate_answer(prompt)

            # If the client supports it, ensure citations are present/consistent.
            format_with_sources = getattr(self.llm, "format_with_sources", None)
            if callable(format_with_sources):
                answer_text = format_with_sources(answer_text, [
                    {
                        "document_name": src["source_file"],
                        "relevance_score": src["score"],
                    }
                    for src in top_sources
                ])
            
            # Prepare response
            response = {
                "answer": answer_text,
                "num_sources": len(retrieved)
            }
            
            if return_sources:
                response["sources"] = [
                    {
                        "document_name": src["source_file"],
                        "excerpt": src["text"][:150] + "..." if len(src["text"]) > 150 else src["text"],
                        "relevance_score": src["score"],
                        "chunk_ids": src["chunk_ids"]
                    }
                    for src in top_sources
                ]
            
            return response
        
        finally:
            # ALWAYS clean up memory, even if error occurs
            try:
                del retrieved, prompt
            except:
                pass
            gc.collect()  # Force garbage collection
    
    def _deduplicate_sources(self, retrieved_chunks: List[Tuple[Dict, float]]) -> List[Dict]:
        """
        Deduplicate and merge similar sources from the same document.
        
        Args:
            retrieved_chunks: List of (chunk_dict, score) tuples
        
        Returns:
            List of deduplicated source dicts with merged information
        """
        # Group chunks by source file
        sources_by_file = {}
        
        for chunk, score in retrieved_chunks:
            source_file = chunk["source_file"]
            
            if source_file not in sources_by_file:
                sources_by_file[source_file] = {
                    "source_file": source_file,
                    "text": chunk["text"],
                    "score": score,  # Keep highest score (first occurrence)
                    "chunk_ids": [chunk["chunk_id"]]
                }
            else:
                # Merge: keep longest text excerpt and track all chunk IDs
                existing = sources_by_file[source_file]
                if len(chunk["text"]) > len(existing["text"]):
                    existing["text"] = chunk["text"]
                existing["chunk_ids"].append(chunk["chunk_id"])
        
        # Convert to list and sort by score (highest first)
        deduplicated = sorted(
            sources_by_file.values(),
            key=lambda x: x["score"],
            reverse=True
        )
        
        return deduplicated


def main():
    """Test RAG pipeline interactively."""
    print("\n" + "="*60)
    print("RAG PIPELINE - Interactive Q&A")
    print("="*60)
    print("Initializing pipeline...")
    
    try:
        pipeline = RAGPipeline()  # Uses parameters.TOP_K_RETRIEVAL
    except Exception as e:
        print(f"Error initializing pipeline: {e}")
        return 1
    
    test_queries = [
        "What is ERP and list its main benefits for businesses?",
        "Explain the key components and modules of an ERP system.",
        "What are the steps to implement manufacturing in an ERP system?",
    ]
    
    for query in test_queries:
        print(f"\n{'='*70}")
        print(f"Q: {query}")
        print(f"{'='*70}")
        
        response = pipeline.answer(query)
        
        print(f"\n{response['answer']}")
        
        print(f"\n{'─'*70}")
        print(f"Sources ({response['num_sources']} documents):")
        for i, source in enumerate(response['sources'], 1):
            print(f"\n[{i}] {source['document_name']}")
            print(f"    Relevance Score: {source['relevance_score']:.3f}")
            print(f"    Excerpt: {source['excerpt']}")
            print(f"    Chunk IDs: {source['chunk_ids']}")
            print(f"     {source['excerpt']}")
            print(f"     Chunks: {', '.join(map(str, source['chunk_ids']))}")
    
    return 0


if __name__ == "__main__":
    exit(main())
