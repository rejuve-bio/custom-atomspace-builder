import argparse
import os
import re
import time
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

from app.prompts.bio_paper_parser_prompts import build_prompt, get_system_prompt
from app.models.bio_parser import FOLTriple, PaperInfo

import arxiv
import requests
import PyPDF2
import openai
from dotenv import load_dotenv

load_dotenv()


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


class PaperProcessor:
    """Orchestrates the complete processing pipeline"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.fetcher = PaperFetcher()
        self.pdf_processor = PDFProcessor()
        self.text_processor = TextProcessor()
        self.fol_extractor = FOLExtractor(api_key)
        self.metta_writer = METTAWriter()
        self.logger = lambda msg: print(f"[PaperProcessor] {msg}")
    
    def process_paper(self, paper_info: PaperInfo, 
                     chunk_size: int = 2000) -> Dict:
        """Process single paper to FOL triples"""
        self.logger(f"Processing: {paper_info.title[:60]}...")
        
        # Extract text
        full_text = self.pdf_processor.download_and_extract_text(
            paper_info.pdf_url, paper_info.title
        )
        
        if not full_text:
            self.logger("No text extracted, using summary")
            full_text = paper_info.summary
        
        # Preprocess
        clean_text = self.text_processor.preprocess_text(full_text)
        
        # Chunk
        chunks = self.text_processor.chunk_text(clean_text, chunk_size)
        
        # Extract FOL triples
        all_triples = []
        for i, chunk in enumerate(chunks):
            self.logger(f"Extracting from chunk {i+1}/{len(chunks)}...")
            triples = self.fol_extractor.extract_triples(chunk)
            all_triples.extend(triples)
            time.sleep(1)  # Rate limiting
        
        # Write METTA file
        metta_path = self.metta_writer.write_metta(
            paper_info.title, all_triples, paper_info
        )
        
        return {
            'title': paper_info.title,
            'triples': all_triples,
            'count': len(all_triples),
            'metta_file': metta_path,
            'paper_info': paper_info
        }
    
    def process_papers(self, query: str, max_papers: int = 3) -> Dict:
        """Process multiple papers"""
        papers = self.fetcher.fetch_papers(query, max_papers)
        
        if not papers:
            self.logger("No papers found!")
            return {}
        
        results = {}
        for idx, paper in enumerate(papers, 1):
            self.logger(f"Processing paper {idx}/{len(papers)}")
            result = self.process_paper(paper)
            results[paper.title] = result
        
        return results
    

class CLI:
    """Command-line interface"""
    
    @staticmethod
    def main():
        parser = argparse.ArgumentParser(
            description="Bio Research Data Semantic FOL Parser",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python bio_paper_parser_service.py --topic "cancer immunotherapy"
  python bio_paper_parser_service.py --topic "CRISPR gene editing" --max-papers 5
  python bio_paper_parser_service.py --paper-title "AlphaFold: Protein structure prediction"
            """
        )
        
        parser.add_argument(
            '--topic',
            type=str,
            help='Research topic to search for'
        )
        
        parser.add_argument(
            '--paper-title',
            type=str,
            help='Specific paper title to search for'
        )
        
        parser.add_argument(
            '--max-papers',
            type=int,
            default=3,
            help='Maximum number of papers to process (default: 3)'
        )
        
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=2000,
            help='Text chunk size for processing (default: 2000)'
        )
        
        parser.add_argument(
            '--output-dir',
            type=str,
            default='./output',
            help='Output directory for METTA files (default: ./output)'
        )
        
        args = parser.parse_args()
        
        # Validate input
        if not args.topic and not args.paper_title:
            parser.print_help()
            print("\nError: Please provide either --topic or --paper-title")
            return
        
        query = args.topic or args.paper_title
        
        print("\n" + "="*60)
        print("Bio Research FOL Parser")
        print("="*60)
        print(f"Query: {query}")
        print(f"Max Papers: {args.max_papers}")
        print("="*60 + "\n")
        
        processor = PaperProcessor()
        processor.metta_writer.output_dir = Path(args.output_dir)
        processor.metta_writer.output_dir.mkdir(exist_ok=True)
        
        results = processor.process_papers(query, args.max_papers)
        
        # Display results
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60 + "\n")
        
        for title, data in results.items():
            print(f"📄 {title[:70]}")
            print(f"   Triples: {data['count']}")
            print(f"   METTA File: {data['metta_file']}")
            print()

if __name__ == "__main__":
    CLI.main()