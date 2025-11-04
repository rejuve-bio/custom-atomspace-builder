from typing import List

import arxiv
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
