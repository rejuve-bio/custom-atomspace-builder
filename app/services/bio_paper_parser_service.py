from datetime import datetime
import os
import re
from typing import List, Optional
from pathlib import Path

from app.prompts.bio_paper_parser_prompts import build_prompt, get_system_prompt
from app.models.bio_parser import FOLTriple, PaperInfo

import arxiv
import requests
import PyPDF2
import openai



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


class TextProcessor:
    """Handles text preprocessing and chunking"""
    
    def __init__(self):
        self.logger = lambda msg: print(f"[TextProcessor] {msg}")
    
    def preprocess_text(self, text: str) -> str:
        """Clean and preprocess paper text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,;:!?()-]', '', text)
        
        # Fix hyphenated words
        text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)
        
        return text.strip()
    
    def chunk_text(self, text: str, chunk_size: int = 2000, 
                   overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            chunks.append(chunk)
            
            if i + chunk_size >= len(words):
                break
        
        self.logger(f"Created {len(chunks)} text chunks")
        return chunks
    

class FOLExtractor:
    """Handles FOL triple extraction using LLM with broad bio-domain focus"""

    def __init__(self, api_key: Optional[str] = None):
        self.client = openai.OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        self.logger = lambda msg: print(f"[FOLExtractor] {msg}")

    def extract_triples(self, text_chunk: str) -> List[FOLTriple]:
        """Extract FOL triples from a text chunk"""
        try:
            prompt = build_prompt(text_chunk)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1400,
                temperature=0.15
            )

            triples_text = response.choices[0].message.content.strip()
            return self._parse_triples(triples_text)

        except Exception as e:
            self.logger(f"Error: {e}")
            return []


    def _parse_triples(self, triples_text: str) -> List[FOLTriple]:
        """Parse extracted triples from LLM output"""
        triples = []
        for line in triples_text.split('\n'):
            line = line.strip()
            match = re.match(r'\(([^,\s]+)\s+([^,\s]+)\s+([^)]+)\)', line)
            if match:
                subject, predicate, obj = match.groups()
                triples.append(FOLTriple(subject.strip(), predicate.strip(), obj.strip()))
        return triples
    

class METTAWriter:
    """Handles METTA file generation"""
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.logger = lambda msg: print(f"[METTAWriter] {msg}")
    
    def write_metta(self, title: str, triples: List[FOLTriple], 
                    paper_info: PaperInfo) -> str:
        """Write FOL triples to METTA file"""
        try:
            # Sanitize filename
            safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
            filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.metta"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w') as f:
                # Header with metadata
                f.write(self._generate_header(title, paper_info, len(triples)))
                f.write("\n\n")
                
                # Define schema
                f.write(self._generate_schema())
                f.write("\n\n")
                
                # Write triples
                f.write("; Research findings\n")
                for triple in triples:
                    f.write(f"{triple.to_metta()}\n")
            
            self.logger(f"Wrote {len(triples)} triples to {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger(f"Error writing METTA file: {e}")
            return ""
    
    @staticmethod
    def _generate_header(title: str, paper_info: PaperInfo, 
                        triple_count: int) -> str:
        """Generate METTA file header"""
        return f"""; Semantic FOL Representation
; Paper: {title}
; Authors: {', '.join(paper_info.authors[:3])}
; Published: {paper_info.published}
; Total Triples: {triple_count}
; Generated: {datetime.now().isoformat()}"""
    
    @staticmethod
    def _generate_schema() -> str:
        """Generate METTA schema definitions"""
        return """; Schema definitions
; (predicate subject object)
; Core predicates used in this representation
(: subject-property (-> Symbol))
(: predicate-property (-> Symbol))
(: object-property (-> Symbol))"""