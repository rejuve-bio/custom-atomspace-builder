import re
from typing import List
from pathlib import Path

import arxiv
import requests
import PyPDF2

from app.models.bio_parser import PaperInfo


class PaperFetcher:
    """Handles paper retrieval from arXiv"""
    
    def __init__(self):
        self.logger = self._get_logger()
    
    @staticmethod
    def _get_logger():
        """Simple logging helper"""
        return lambda msg: print(f"[PaperFetcher] {msg}")
    
    def fetch_papers(self, query: str, max_results: int = 5) -> List[PaperInfo]:
        """Fetch research papers from arXiv"""
        try:
            self.logger(f"Searching arXiv for: {query}")
            
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            papers = []
            for result in search.results():
                paper = PaperInfo(
                    title=result.title,
                    summary=result.summary,
                    pdf_url=result.pdf_url,
                    published=str(result.published),
                    authors=[author.name for author in result.authors]
                )
                papers.append(paper)
            
            self.logger(f"Found {len(papers)} papers")
            return papers
            
        except Exception as e:
            self.logger(f"Error fetching papers: {e}")
            return []

class PDFProcessor:
    """Handles PDF download and text extraction"""
    
    def __init__(self, temp_dir: str = "./temp_pdfs"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.logger = lambda msg: print(f"[PDFProcessor] {msg}")
    
    def download_and_extract_text(self, pdf_url: str, paper_title: str) -> str:
        """Download PDF and extract text content"""
        try:
            self.logger(f"Downloading PDF from {pdf_url[:50]}...")
            
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            # Save temporarily with sanitized filename
            temp_file = self.temp_dir / f"{self._sanitize_filename(paper_title)}.pdf"
            
            with open(temp_file, 'wb') as f:
                f.write(response.content)
            
            # Extract text
            text = self._extract_text_from_pdf(temp_file)
            
            # Cleanup
            temp_file.unlink()
            
            self.logger(f"Extracted {len(text)} characters")
            return text
            
        except Exception as e:
            self.logger(f"Error: {e}")
            return ""
    
    @staticmethod
    def _extract_text_from_pdf(pdf_path: Path) -> str:
        """Extract text from PDF file"""
        text = ""
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    text += page.extract_text() + "\n"
                except Exception as e:
                    print(f"Warning: Could not extract page {page_num}")
        return text
    
    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Sanitize filename for file system"""
        return re.sub(r'[^\w\s-]', '', filename)[:50]
