"""
ATIK AI - Çoklu Ajanlı Hibrit Karar Destek Sistemi

Faz 1: W2RKG (Knowledge Graph)
Faz 2: Bi-Encoder (Prediction)
Faz 3: Multi-Agent RAG
Faz 4: SWAN (Economic Feasibility)
"""
import logging

__version__ = "1.0.0"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# =============================================================================
# LAZY IMPORTS - Avoid circular imports
# =============================================================================

def __getattr__(name):
    """Lazy module loading"""
    
    # Core
    if name == "DatabaseManager":
        from .core.database import DatabaseManager
        return DatabaseManager
    if name == "models":
        from .core import models
        return models
    if name == "exceptions":
        from .core import exceptions
        return exceptions
    
    # Config
    if name == "config":
        from .config import config
        return config
    
    # Knowledge (W2RKG)
    if name == "KnowledgeGraph":
        from .knowledge import KnowledgeGraph
        return KnowledgeGraph
    if name == "TripleExtractor":
        from .knowledge import TripleExtractor
        return TripleExtractor
    if name == "EntityFusion":
        from .knowledge import EntityFusion
        return EntityFusion
    if name == "AcademicDataCollector":
        from .knowledge import AcademicDataCollector
        return AcademicDataCollector
    
    # Prediction (Bi-Encoder)
    if name == "BiEncoder":
        from .prediction import BiEncoder
        return BiEncoder
    if name == "WastePredictor":
        from .prediction import WastePredictor
        return WastePredictor
    if name == "EmbeddingManager":
        from .prediction import EmbeddingManager
        return EmbeddingManager
    if name == "Trainer":
        from .prediction import Trainer
        return Trainer
    
    # Economics (SWAN)
    if name == "FeasibilityAnalyzer":
        from .economics import FeasibilityAnalyzer
        return FeasibilityAnalyzer
    if name == "PricingEngine":
        from .economics import PricingEngine
        return PricingEngine
    if name == "LogisticsCalculator":
        from .economics import LogisticsCalculator
        return LogisticsCalculator
    if name == "RouteOptimizer":
        from .economics import RouteOptimizer
        return RouteOptimizer
    
    # Matching
    if name == "MatchingEngine":
        from .matching import MatchingEngine
        return MatchingEngine
    if name == "TechnicalMatcher":
        from .matching import TechnicalMatcher
        return TechnicalMatcher
    if name == "TemporalMatcher":
        from .matching import TemporalMatcher
        return TemporalMatcher
    
    # Distance
    if name == "DistanceCalculator":
        from .distance import DistanceCalculator
        return DistanceCalculator
    if name == "DistanceCache":
        from .distance import DistanceCache
        return DistanceCache
    if name == "DistanceMatrixBuilder":
        from .distance import DistanceMatrixBuilder
        return DistanceMatrixBuilder
    
    # Agents
    if name == "AgentOrchestrator":
        from .agents import AgentOrchestrator
        return AgentOrchestrator
    if name == "ExtractionAgent":
        from .agents import ExtractionAgent
        return ExtractionAgent
    if name == "MatchingAgent":
        from .agents import MatchingAgent
        return MatchingAgent
    if name == "FeasibilityAgent":
        from .agents import FeasibilityAgent
        return FeasibilityAgent
    
    # API
    if name == "app":
        from .api.routes import api_router
        from fastapi import FastAPI
        _app = FastAPI(title="ATIK AI", version=__version__)
        _app.include_router(api_router)
        return _app
    
    raise AttributeError(f"module 'atik_ai' has no attribute '{name}'")


__all__ = [
    # Version
    "__version__",
    
    # Config
    "config",
    
    # Core
    "DatabaseManager",
    "models",
    "exceptions",
    
    # Knowledge
    "KnowledgeGraph",
    "TripleExtractor",
    "EntityFusion",
    "AcademicDataCollector",
    
    # Prediction
    "BiEncoder",
    "WastePredictor",
    "EmbeddingManager",
    "Trainer",
    
    # Economics
    "FeasibilityAnalyzer",
    "PricingEngine",
    "LogisticsCalculator",
    "RouteOptimizer",
    
    # Matching
    "MatchingEngine",
    "TechnicalMatcher",
    "TemporalMatcher",
    
    # Distance
    "DistanceCalculator",
    "DistanceCache",
    "DistanceMatrixBuilder",
    
    # Agents
    "AgentOrchestrator",
    "ExtractionAgent",
    "MatchingAgent",
    "FeasibilityAgent",
    
    # API
    "app",
]
