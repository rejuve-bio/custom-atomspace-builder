from dataclasses import dataclass
from typing import List

@dataclass
class PaperInfo:
    """Data structure for paper metadata"""
    title: str
    summary: str
    pdf_url: str
    published: str
    authors: List[str]


@dataclass
class FOLTriple:
    """Data structure for FOL triples"""
    subject: str
    predicate: str
    obj: str
    
    def to_tuple(self) -> tuple:
        return (self.subject, self.predicate, self.obj)
    
    def to_metta(self) -> str:
        """Convert triple to METTA format"""
        return f"({self.subject} {self.predicate} {self.obj})"
