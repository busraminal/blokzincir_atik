"""
ATIK AI - Agno Base Components
Multi-Agent RAG sistemi için Agno framework entegrasyonu.

Bu modül eskiye uyumluluk için bazı yardımcı sınıfları sağlar.
Asıl agent tanımları agents.py, team.py ve tools.py içindedir.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


# ============================================================================
# Enums - Backward compatibility
# ============================================================================

class AgentRole(Enum):
    """Ajan rolleri (Agno Team mode uyumlu)"""
    EXTRACTOR = "extractor"        # Bilgi çıkarma
    MATCHER = "matcher"            # Eşleştirme
    FEASIBILITY = "feasibility"    # Fizibilite
    COORDINATOR = "coordinator"    # Koordinatör (Team Leader)


class WorkflowState(Enum):
    """İş akışı durumları"""
    IDLE = "idle"
    EXTRACTING = "extracting"
    MATCHING = "matching"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ExtractionResult:
    """Bilgi çıkarma sonucu"""
    query: str
    sources_used: List[str] = field(default_factory=list)
    
    # Bilgi kaynakları
    embedding_results: List[Dict] = field(default_factory=list)
    academic_results: List[Dict] = field(default_factory=list)
    web_results: List[Dict] = field(default_factory=list)
    
    # Birleştirilmiş sonuç
    merged_answer: str = ""
    confidence: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "sources_used": self.sources_used,
            "embedding_results": self.embedding_results,
            "academic_results": self.academic_results,
            "merged_answer": self.merged_answer,
            "confidence": self.confidence
        }


@dataclass
class MatchResult:
    """Eşleştirme sonucu"""
    source_facility_id: int
    waste_type_id: int
    matches: List[Dict] = field(default_factory=list)
    total_found: int = 0
    
    def to_dict(self) -> dict:
        return {
            "source_facility_id": self.source_facility_id,
            "waste_type_id": self.waste_type_id,
            "matches": self.matches,
            "total_found": self.total_found
        }


@dataclass
class FeasibilityResult:
    """Fizibilite analiz sonucu"""
    match_id: str
    is_feasible: bool
    
    # Ekonomik metrikler
    source_profit: float = 0.0
    receiver_profit: float = 0.0
    suggested_price: float = 0.0
    
    # Fiyat aralıkları
    price_wbes: float = 0.0  # Kaynak break-even
    price_wber: float = 0.0  # Alıcı break-even
    
    # Analiz detayları
    transport_cost: float = 0.0
    processing_cost: float = 0.0
    
    recommendation: str = ""
    
    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "is_feasible": self.is_feasible,
            "source_profit": self.source_profit,
            "receiver_profit": self.receiver_profit,
            "suggested_price": self.suggested_price,
            "price_wbes": self.price_wbes,
            "price_wber": self.price_wber,
            "transport_cost": self.transport_cost,
            "processing_cost": self.processing_cost,
            "recommendation": self.recommendation
        }


@dataclass
class WorkflowResult:
    """İş akışı sonucu"""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: WorkflowState = WorkflowState.IDLE
    
    # Ara sonuçlar
    extraction_result: Optional[ExtractionResult] = None
    matching_result: Optional[MatchResult] = None
    feasibility_result: Optional[FeasibilityResult] = None
    
    # Final sonuç
    final_output: Dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    # Meta
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0
    error: Optional[str] = None
    
    def complete(self):
        """İşlemi tamamla"""
        self.completed_at = datetime.now()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000
        self.state = WorkflowState.COMPLETED
    
    def fail(self, error: str):
        """İşlemi başarısız olarak işaretle"""
        self.error = error
        self.state = WorkflowState.FAILED
        self.completed_at = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "state": self.state.value,
            "extraction_result": self.extraction_result.to_dict() if self.extraction_result else None,
            "matching_result": self.matching_result.to_dict() if self.matching_result else None,
            "feasibility_result": self.feasibility_result.to_dict() if self.feasibility_result else None,
            "final_output": self.final_output,
            "recommendations": self.recommendations,
            "duration_ms": self.duration_ms,
            "error": self.error
        }


# ============================================================================
# Session State için yardımcı sınıf
# ============================================================================

@dataclass
class AtikAIState:
    """
    Agno session_state için ATIK AI durumu.
    
    Bu sınıf, Agno'nun session_state mekanizması ile kullanılır.
    """
    # Kullanıcı/Oturum bilgisi
    user_id: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Mevcut işlem konteksti
    current_facility_id: Optional[int] = None
    current_waste_type_id: Optional[int] = None
    
    # Son sonuçlar (cache gibi)
    last_extraction: Optional[Dict] = None
    last_matches: List[Dict] = field(default_factory=list)
    last_feasibility: Optional[Dict] = None
    
    # Tercihler
    max_distance_km: float = 100.0
    min_confidence: float = 0.7
    
    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "current_facility_id": self.current_facility_id,
            "current_waste_type_id": self.current_waste_type_id,
            "last_extraction": self.last_extraction,
            "last_matches": self.last_matches,
            "last_feasibility": self.last_feasibility,
            "max_distance_km": self.max_distance_km,
            "min_confidence": self.min_confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AtikAIState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
