"""
RAG (Retrieval-Augmented Generation) pipeline.

Combines semantic search with LLM generation for question-answering with citations.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Tuple, Dict
from src.vectorstore import VectorStore
from src.ollama_client import OllamaClient


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for Q&A with citations."""
    
    def __init__(
        self,
        vectorstore: VectorStore = None,
        llm_client: OllamaClient = None,
        top_k: int = 5
    ):
        """
        Initialize RAG pipeline.
        
        Args:
            vectorstore: VectorStore instance (or load from disk)
            llm_client: OllamaClient instance (or create with defaults)
            top_k: Number of documents to retrieve for context
        """
        self.top_k = top_k
        
        # Initialize or load vector store
        if vectorstore is None:
            self.vectorstore = VectorStore()
            self.vectorstore.load()
        else:
            self.vectorstore = vectorstore
        
        # Initialize or create LLM client
        if llm_client is None:
            self.llm = OllamaClient()
        else:
            self.llm = llm_client
    
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
        # Get unique document names for source list (top 2-3 only)
        unique_docs = []
        seen_docs = set()
        for chunk, score in retrieved_chunks:
            doc_name = chunk['source_file']
            if doc_name not in seen_docs:
                unique_docs.append(doc_name)
                seen_docs.add(doc_name)
            if len(unique_docs) >= 3:
                break
        
        # Build context section with XML-style tags (no scores visible to LLM)
        context_lines = ["<context>"]
        for i, (chunk, score) in enumerate(retrieved_chunks, 1):
            context_lines.append(f"\n[Document {i}]")
            context_lines.append(f"Source: {chunk['source_file']}")
            context_lines.append(f"Content: {chunk['text']}")
        context_lines.append("\n</context>")
        
        context_block = "\n".join(context_lines)
        
        # Build available sources list for reference
        sources_list = "\n".join([f"- {doc}" for doc in unique_docs])
        
        # Build improved structured prompt with better clarity and quality
        prompt = f"""{context_block}

AVAILABLE SOURCES:
{sources_list}

QUESTION:
{user_question}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPONSE INSTRUCTIONS - FOLLOW PRECISELY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are an expert ERP consultant providing precise, actionable guidance.

MANDATORY RESPONSE STRUCTURE:

## [Clear, Concise Title - Under 10 Words]

### Overview
[Write 2-3 sentences that directly answer the question. Be specific and comprehensive. Focus on WHAT and WHY before HOW.]

### Key Prerequisites
- [List 2-3 essential requirements, system roles, or access permissions needed]
- [Each item should be concrete and verifiable]

### Step-by-Step Procedure
1. [Action verb] [Specific instruction with navigation path if applicable]
2. [Each step should be atomic and executable]
3. [Include system responses or expected outcomes where relevant]
4. [Use technical terminology correctly (transaction codes, field names, menu paths)]
5. [Continue until complete - typically 4-8 steps for most procedures]

### Important Considerations
- [Critical warnings, data impacts, or timing constraints]
- [Common pitfalls to avoid]
- [Integration points with other modules]
- [Maximum 5 points, each focused on risk mitigation or optimization]

### Related Topics
- [2-3 related procedures or concepts the user might need next]

### Sources
- [Document name 1]
- [Document name 2]
- [Document name 3 - MAXIMUM 3]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTENT QUALITY STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STRICT RULES:
✓ Answer ONLY using information from <context> above - zero hallucination
✓ Use specific terminology from source documents (exact field names, transaction codes, module names)
✓ Write in present tense, active voice: "Navigate to..." not "You should navigate to..."
✓ Include quantifiable details when available (time estimates, record limits, validation rules)
✓ Maintain professional consultant tone - authoritative but approachable
✓ Adapt detail level to question complexity (overview questions get broad answers, technical questions get specifics)

FORBIDDEN:
✗ Generic filler phrases: "simply", "just", "easily", "of course", "as you know"
✗ Hedging language: "might", "possibly", "perhaps", "maybe" (use "typically", "generally" if needed)
✗ Combining information from different ERP vendors (choose most relevant system)
✗ Adding external knowledge not present in context
✗ Vague instructions: "Configure settings" → "Navigate to SPRO → Financial Accounting → Configure Company Code"

FORMATTING RULES:
• One blank line between all sections
• Use ## for title, ### for section headers
• Numbered lists for sequential steps (1. 2. 3.)
• Bullet points (-) for non-sequential items
• Bold (**text**) for critical warnings or key terms
• Code/system references in backticks: `T-code: FB50`

SPECIAL CASES:
→ If question is conceptual (What/Why): Focus on Overview section with 4-5 detailed sentences
→ If question is procedural (How): Emphasize Step-by-Step with 6-8 specific actions
→ If question involves troubleshooting: Add "Common Issues" subsection under Important Considerations
→ If insufficient context: Respond ONLY with: "The available documentation does not contain sufficient information to answer '[question]'. Please check: [list 2-3 related topics that might help]"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUALITY CHECKLIST (Verify before responding):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

□ Title directly reflects the question topic
□ Overview provides complete answer in 2-3 sentences
□ All technical terms match source documents exactly
□ Steps are executable by someone with basic ERP knowledge
□ No information from outside the provided context
□ Maximum 3 sources cited
□ Professional tone maintained throughout
□ Response length: 150-300 words (adjust based on question complexity)

Now provide your expert response:
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
        # Retrieve relevant documents
        retrieved = self.retrieve(query)
        
        # Build structured prompt with context tags
        prompt = self.build_structured_prompt(query, retrieved)
        
        # Generate answer
        answer_text = self.llm.generate_answer(prompt)
        
        # Prepare response
        response = {
            "answer": answer_text,
            "num_sources": len(retrieved)
        }
        
        if return_sources:
            # Deduplicate and merge similar sources
            deduplicated_sources = self._deduplicate_sources(retrieved)
            
            # Keep only top 2-3 most relevant sources
            top_sources = deduplicated_sources[:3]
            
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
        pipeline = RAGPipeline(top_k=5)
    except Exception as e:
        print(f"Error initializing pipeline: {e}")
        return 1
    
    test_queries = [
        "What is ERP and what are its benefits?",
        "How do I implement manufacturing in ERP?",
        "What are common ERP challenges?",
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Q: {query}")
        print(f"{'='*60}")
        
        response = pipeline.answer(query)
        
        print(f"\nA: {response['answer']}")
        
        print(f"\nSources ({response['num_sources']} documents):")
        for i, source in enumerate(response['sources'], 1):
            print(f"  {i}. {source['document_name']} (Score: {source['relevance_score']:.3f})")
            print(f"     {source['excerpt']}")
            print(f"     Chunks: {', '.join(map(str, source['chunk_ids']))}")
    
    return 0


if __name__ == "__main__":
    exit(main())
