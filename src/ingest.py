"""
Document ingestion and chunking pipeline for RAG.

Processes PDF files:
1. Extract text and structure with Docling (tables, headings, etc.)
2. Save converted documents as markdown
3. Clean headers, footers, page numbers, extra whitespace
4. Split into overlapping chunks
5. Save as JSON for vector indexing
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
try:
    import fitz  # PyMuPDF (fallback)
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("Warning: PyMuPDF not installed. PDF fallback processing will be disabled.")
from docling.document_converter import DocumentConverter


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


class DoclingProcessor:
    """Process PDFs using Docling for structured extraction."""
    
    def __init__(self, output_dir: str = "data/converted_docs"):
        """
        Initialize Docling processor.
        
        Args:
            output_dir: Directory to save converted markdown files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.converter = DocumentConverter()
    
    def convert_pdf(self, pdf_path: Path) -> Tuple[str, Path]:
        """
        Convert PDF to structured markdown using Docling.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Tuple of (markdown_text, saved_markdown_path)
        
        Raises:
            RuntimeError: If conversion fails
        """
        try:
            print(f"  Converting {pdf_path.name} with Docling...")
            
            # Convert PDF to structured format
            result = self.converter.convert(str(pdf_path))
            
            # Export to markdown
            markdown_text = result.document.export_to_markdown()
            
            # Save markdown file
            md_filename = pdf_path.stem + ".md"
            md_path = self.output_dir / md_filename
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_text)
            
            print(f"  Saved converted document: {md_path.name}")
            
            return markdown_text, md_path
            
        except Exception as e:
            raise RuntimeError(f"Docling conversion failed for {pdf_path.name}: {e}") from e


class DocumentChunker:
    """Split documents into overlapping chunks."""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target words per chunk
            overlap: Words to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
    
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
    """Main ingestion pipeline using Docling."""
    
    def __init__(
        self,
        raw_docs_dir: str = "data/raw_docs",
        output_dir: str = "data/processed_chunks",
        converted_docs_dir: str = "data/converted_docs",
        chunk_size: int = 500,
        overlap: int = 100
    ):
        """
        Initialize ingester.
        
        Args:
            raw_docs_dir: Directory containing PDF files
            output_dir: Directory to save processed chunks
            converted_docs_dir: Directory to save converted markdown files
            chunk_size: Words per chunk
            overlap: Word overlap between chunks
        """
        self.raw_docs_dir = Path(raw_docs_dir)
        self.output_dir = Path(output_dir)
        self.converted_docs_dir = Path(converted_docs_dir)
        self.chunk_size = chunk_size
        self.overlap = overlap
        
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
        self.chunker = DocumentChunker(chunk_size=chunk_size, overlap=overlap)
        self.docling_processor = DoclingProcessor(output_dir=str(converted_docs_dir))
    
    def extract_pdf_text(self, pdf_path: Path) -> str:
        """
        Extract text from PDF with page info.
        
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
            
            # Clean the text
            cleaned = self.cleaner.clean_text(full_text)
            return cleaned
        
        except Exception as e:
            raise RuntimeError(f"Failed to read {pdf_path.name}: {e}") from e
    
    def ingest_document(self, pdf_path: Path) -> Tuple[List[Dict], int]:
        """
        Ingest a single PDF document using Docling.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Tuple of (chunks list, word count)
        """
        print(f"  Processing {pdf_path.name} with Docling...")
        
        # Convert PDF to markdown using Docling
        markdown_text, md_path = self.docling_processor.convert_pdf(pdf_path)
        
        # Clean the markdown text
        cleaned_text = self.cleaner.clean_text(markdown_text)
        word_count = len(cleaned_text.split())
        
        print(f"  Extracted: {word_count} words from structured markdown")
        
        print(f"  Creating chunks...")
        chunks = self.chunker.chunk_text(cleaned_text, pdf_path.name)
        
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
    ingester = DocumentIngester(
        raw_docs_dir="data/raw_docs",
        output_dir="data/processed_chunks",
        chunk_size=500,
        overlap=100
    )
    
    try:
        stats, chunks = ingester.ingest_all()
        ingester.print_summary(stats)
        return 0
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1


if __name__ == "__main__":
    exit(main())
