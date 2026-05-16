# Knowledge Module (W2RKG)
from .graph import KnowledgeGraph
from .extractor import TripleExtractor
from .fusion import EntityFusion
from .academic import AcademicDataCollector

__all__ = [
    "KnowledgeGraph",
    "TripleExtractor", 
    "EntityFusion",
    "AcademicDataCollector"
]
