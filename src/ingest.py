"""
Document ingestion and chunking pipeline for RAG.

Processes PDF files:
1. Extract text with PyMuPDF (fast, no OCR)
2. Clean headers, footers, page numbers, extra whitespace
3. Split into overlapping chunks
4. Save as JSON for vector indexing
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import fitz  # PyMuPDF

# Add parent directory to path so imports work from src/
sys.path.insert(0, str(Path(__file__).parent.parent))


class TextCleaner:
    """Clean extracted text from PDFs."""
    
    @staticmethod
    def clean_page_numbers(text: str) -> str:
        """Remove page numbers (e.g., '- 1 -', 'Page 1', etc.)."""
        # Remove patterns like "- 1 -", "Page 1", "1", etc. on their own line
        text = re.sub(r'^\s*(?:Page\s*\d+|p\.\s*\d+|-\s*\d+\s*-|\[\d+\])\s*$', '', text, flags=re.MULTILINE)
        return text
    
    @staticmethod
    def remove_headers_footers(text: str) -> str:
        """Remove common header/footer patterns."""
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip if line looks like header/footer
            if re.match(r'^\s*(?:Chapter|Table of Contents|Appendix|Index)', line, re.IGNORECASE):
                continue
            if len(line.strip()) < 3:  # Skip very short lines (likely page numbers/breaks)
                continue
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace: multiple spaces, tabs, extra newlines."""
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        # Replace multiple newlines with double newline (preserve paragraph breaks)
        text = re.sub(r'\n\n+', '\n\n', text)
        # Remove leading/trailing whitespace per line
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(lines)
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Apply all cleaning steps."""
        text = TextCleaner.clean_page_numbers(text)
        text = TextCleaner.remove_headers_footers(text)
        text = TextCleaner.normalize_whitespace(text)
        return text.strip()


class DocumentChunker:
    """Split documents into overlapping chunks."""
    
    def __init__(self, chunk_size: int = None, overlap: int = None):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target words per chunk (uses parameters.CHUNK_SIZE if not set)
            overlap: Words to overlap between chunks (uses parameters.CHUNK_OVERLAP if not set)
        """
        try:
            from . import parameters
        except ImportError:
            import parameters
        self.chunk_size = chunk_size if chunk_size is not None else parameters.CHUNK_SIZE
        self.overlap = overlap if overlap is not None else parameters.CHUNK_OVERLAP
    
    def chunk_text(self, text: str, source_file: str) -> List[Dict]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full text to chunk
            source_file: Source filename for attribution
        
        Returns:
            List of chunk dicts with chunk_id, text, source_file
        """
        # Split into words
        words = text.split()
        chunks = []
        chunk_id = 0
        
        i = 0
        while i < len(words):
            # Get chunk_size words
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words).strip()
            
            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": chunk_text,
                    "source_file": source_file
                })
                chunk_id += 1
            
            # Move forward by (chunk_size - overlap)
            step = self.chunk_size - self.overlap
            i += step
        
        return chunks


class DocumentIngester:
    """Main ingestion pipeline using PyMuPDF."""
    
    def __init__(
        self,
        raw_docs_dir: str = "data/raw_docs",
        output_dir: str = "data/processed_chunks",
        converted_docs_dir: str = "data/converted_docs",
        chunk_size: int = None,
        overlap: int = None
    ):
        """
        Initialize ingester.
        
        Args:
            raw_docs_dir: Directory containing PDF files
            output_dir: Directory to save processed chunks
            converted_docs_dir: Directory to save extracted markdown files
            chunk_size: Words per chunk (uses parameters.CHUNK_SIZE if not set)
            overlap: Word overlap between chunks (uses parameters.CHUNK_OVERLAP if not set)
        """
        try:
            from . import parameters
        except ImportError:
            import parameters
        self.raw_docs_dir = Path(raw_docs_dir)
        self.output_dir = Path(output_dir)
        self.converted_docs_dir = Path(converted_docs_dir)
        self.chunk_size = chunk_size if chunk_size is not None else parameters.CHUNK_SIZE
        self.overlap = overlap if overlap is not None else parameters.CHUNK_OVERLAP
        
        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.converted_docs_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate input directory
        if not self.raw_docs_dir.exists():
            raise RuntimeError(
                f"Input directory not found: {self.raw_docs_dir.resolve()}\n"
                f"Create it and add PDF files."
            )
        
        self.cleaner = TextCleaner()
        self.chunker = DocumentChunker(chunk_size=self.chunk_size, overlap=self.overlap)
    
    def extract_pdf_text(self, pdf_path: Path) -> str:
        """
        Extract text from PDF with page info and save as markdown.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Extracted and cleaned text
        
        Raises:
            RuntimeError: If PDF cannot be read
        """
        try:
            doc = fitz.open(str(pdf_path))
            pages_text = []
            
            for page_num, page in enumerate(doc, 1):
                text = page.get_text()
                # Add page break marker
                pages_text.append(f"[PAGE {page_num}]\n{text}")
            
            doc.close()
            full_text = '\n'.join(pages_text)
            
            # Save raw markdown to converted_docs
            md_filename = pdf_path.stem + ".md"
            md_path = self.converted_docs_dir / md_filename
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(full_text)
            
            # Clean the text
            cleaned = self.cleaner.clean_text(full_text)
            return cleaned
        
        except Exception as e:
            raise RuntimeError(f"Failed to read {pdf_path.name}: {e}") from e
    
    def ingest_document(self, pdf_path: Path) -> Tuple[List[Dict], int]:
        """
        Ingest a single PDF document using PyMuPDF.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Tuple of (chunks list, word count)
        """
        print(f"  Extracting text from {pdf_path.name}...")
        
        # Extract text using PyMuPDF
        text = self.extract_pdf_text(pdf_path)
        word_count = len(text.split())
        
        print(f"  Extracted: {word_count} words")
        print(f"  Creating chunks...")
        chunks = self.chunker.chunk_text(text, pdf_path.name)
        
        print(f"  Created: {len(chunks)} chunks")
        return chunks, word_count
    
    def ingest_all(self) -> Dict:
        """
        Ingest all PDFs in raw_docs directory.
        
        Returns:
            Summary statistics dict
        """
        pdf_files = list(self.raw_docs_dir.glob("*.pdf"))
        
        if not pdf_files:
            raise RuntimeError(
                f"No PDF files found in {self.raw_docs_dir.resolve()}\n"
                f"Add PDF files to process."
            )
        
        print(f"\n[Ingestion] Found {len(pdf_files)} PDF file(s)\n")
        
        all_chunks = []
        stats = {
            "total_files": len(pdf_files),
            "total_chunks": 0,
            "total_words": 0,
            "files": {}
        }
        
        for pdf_path in pdf_files:
            print(f"[Processing] {pdf_path.name}")
            chunks, word_count = self.ingest_document(pdf_path)
            all_chunks.extend(chunks)
            
            stats["total_chunks"] += len(chunks)
            stats["total_words"] += word_count
            stats["files"][pdf_path.name] = {
                "chunks": len(chunks),
                "words": word_count
            }
            print()
        
        # Save chunks
        output_file = self.output_dir / "chunks.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_chunks, f, indent=2, ensure_ascii=False)
        
        stats["output_file"] = str(output_file)
        
        return stats, all_chunks
    
    def print_summary(self, stats: Dict) -> None:
        """Print ingestion summary."""
        print("\n" + "="*60)
        print("INGESTION COMPLETE")
        print("="*60)
        print(f"Files processed:    {stats['total_files']}")
        print(f"Total chunks:       {stats['total_chunks']}")
        print(f"Total words:        {stats['total_words']:,}")
        print(f"Avg words/chunk:    {stats['total_words'] // max(stats['total_chunks'], 1):.0f}")
        print(f"\nOutput file:        {stats['output_file']}")
        
        print(f"\nPer-file breakdown:")
        for filename, file_stats in stats["files"].items():
            print(f"  {filename}")
            print(f"    - Chunks: {file_stats['chunks']}")
            print(f"    - Words:  {file_stats['words']:,}")


def main():
    """Run document ingestion pipeline."""
    # Check both directories - prioritize data/pdfs (upload directory) then fall back to data/raw_docs
    upload_dir = Path("data/pdfs")
    raw_dir = Path("data/raw_docs")
    
    if upload_dir.exists() and list(upload_dir.glob("*.pdf")):
        input_dir = upload_dir
    elif raw_dir.exists():
        input_dir = raw_dir
    else:
        input_dir = upload_dir  # Default to upload dir if neither exists
    
    ingester = DocumentIngester(
        raw_docs_dir=str(input_dir),
        output_dir="data/processed_chunks",
        converted_docs_dir="data/converted_docs"
        # Uses parameters.CHUNK_SIZE and parameters.CHUNK_OVERLAP
    )
    
    try:
        stats, chunks = ingester.ingest_all()
        ingester.print_summary(stats)
        
        # Automatically build vectorstore
        print("\n" + "="*60)
        print("BUILDING VECTORSTORE")
        print("="*60)
        
        from src.vectorstore import VectorStore
        store = VectorStore()
        store.ingest_chunks(chunks)
        
        print("\n✅ Vectorstore built successfully!")
        print("You can now run: python -m uvicorn app.api:app --host 0.0.0.0 --port 8000")
        
        return 0
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1


if __name__ == "__main__":
    exit(main())
