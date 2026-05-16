"""
ATIK AI - Agno Team
Agno Team yapısı ile Multi-Agent koordinasyonu.

Team, birden fazla ajanın koordineli çalışmasını sağlar.
"""
import logging
from typing import Optional, List, Dict, Any

from agno.agent import Agent
from agno.team import Team, TeamMode
from agno.workflow import Workflow

from .agents import (
    create_extraction_agent,
    create_matching_agent,
    create_feasibility_agent,
    create_coordinator_agent,
    get_default_model,
    get_azure_model
)
from ..config import config

logger = logging.getLogger(__name__)


# ============================================================================
# Team Modes
# ============================================================================

class AtikAITeamMode:
    """ATIK AI için özel Team modları"""
    
    # Tam pipeline - tüm ajanlar sırayla çalışır
    FULL_PIPELINE = "full_pipeline"
    
    # Sadece eşleştirme
    MATCH_ONLY = "match_only"
    
    # Sadece bilgi çıkarma
    EXTRACT_ONLY = "extract_only"
    
    # Sadece fizibilite
    FEASIBILITY_ONLY = "feasibility_only"
    
    # Otomatik - Coordinator karar verir
    AUTO = "auto"


# ============================================================================
# ATIK AI Team
# ============================================================================

def create_atik_team(
    model=None,
    mode: TeamMode = TeamMode.coordinate,
    include_extraction: bool = True,
    include_matching: bool = True,
    include_feasibility: bool = True,
    **kwargs
) -> Team:
    """
    ATIK AI Multi-Agent Team oluştur.
    
    Args:
        model: LLM modeli (tüm ajanlar için)
        mode: Team çalışma modu
            - TeamMode.coordinate: Coordinator görevleri dağıtır
            - TeamMode.route: Tek ajana yönlendir
            - TeamMode.broadcast: Tüm ajanlara gönder
        include_extraction: Extraction Agent dahil edilsin mi
        include_matching: Matching Agent dahil edilsin mi  
        include_feasibility: Feasibility Agent dahil edilsin mi
        **kwargs: Ek Team parametreleri
    
    Returns:
        Agno Team instance
    """
    model = model or get_default_model()
    
    # Üye ajanları oluştur
    members = []
    
    if include_extraction:
        members.append(create_extraction_agent(model=model))
    
    if include_matching:
        members.append(create_matching_agent(model=model))
    
    if include_feasibility:
        members.append(create_feasibility_agent(model=model))
    
    if not members:
        raise ValueError("En az bir ajan dahil edilmelidir")
    
    # Team oluştur
    team = Team(
        name="ATIK AI Team",
        mode=mode,
        model=model,
        members=members,
        instructions="""Sen ATIK AI ekibinin koordinatörüsün.

## Ekibin
- **ExtractionAgent**: Atık yönetimi bilgisi çıkarır, W2RKG knowledge graph sorgular
- **MatchingAgent**: Atık-tesis eşleştirmesi yapar, teknik uyumluluk kontrol eder
- **FeasibilityAgent**: SWAN modeli ile ekonomik fizibilite analizi yapar

## Koordinasyon Kuralları
1. Kullanıcı sorusunu analiz et
2. En uygun ajan(lar)ı seç:
   - Bilgi soruları → ExtractionAgent
   - Eşleştirme istekleri → MatchingAgent
   - Maliyet/fizibilite soruları → FeasibilityAgent
   - Tam analiz → Sırayla: Extraction → Matching → Feasibility

3. Sonuçları birleştir ve özet sun

## Çıktı Formatı
- Net bir özet
- Detaylı bulgular
- Somut öneriler
- Sonraki adımlar

Türkçe yanıt ver. Teknik terimleri açıkla.""",
        markdown=True,
        show_tool_calls=True,
        **kwargs
    )
    
    return team


# ============================================================================
# Specialized Teams
# ============================================================================

def create_matching_team(model=None, **kwargs) -> Team:
    """
    Eşleştirme odaklı Team oluştur.
    
    Matching + Feasibility ajanlarını içerir.
    """
    return create_atik_team(
        model=model,
        mode=TeamMode.coordinate,
        include_extraction=False,
        include_matching=True,
        include_feasibility=True,
        **kwargs
    )


def create_research_team(model=None, **kwargs) -> Team:
    """
    Araştırma odaklı Team oluştur.
    
    Sadece Extraction Agent içerir.
    """
    return create_atik_team(
        model=model,
        mode=TeamMode.route,
        include_extraction=True,
        include_matching=False,
        include_feasibility=False,
        **kwargs
    )


# ============================================================================
# ATIK AI Workflows
# ============================================================================

def create_full_analysis_workflow(model=None) -> Workflow:
    """
    Tam analiz iş akışı oluştur.
    
    Sıralı adımlar:
    1. Extraction: Bilgi topla
    2. Matching: Eşleşmeleri bul
    3. Feasibility: Ekonomik analiz
    
    Returns:
        Agno Workflow instance
    """
    model = model or get_default_model()
    
    extraction_agent = create_extraction_agent(model=model)
    matching_agent = create_matching_agent(model=model)
    feasibility_agent = create_feasibility_agent(model=model)
    
    workflow = Workflow(
        name="ATIK AI Full Analysis",
        steps=[
            extraction_agent,
            matching_agent,
            feasibility_agent
        ]
    )
    
    return workflow


def create_quick_match_workflow(model=None) -> Workflow:
    """
    Hızlı eşleştirme iş akışı.
    
    Sıralı adımlar:
    1. Matching: Eşleşmeleri bul
    2. Feasibility: Ekonomik analiz
    
    Returns:
        Agno Workflow instance
    """
    model = model or get_default_model()
    
    matching_agent = create_matching_agent(model=model)
    feasibility_agent = create_feasibility_agent(model=model)
    
    workflow = Workflow(
        name="ATIK AI Quick Match",
        steps=[
            matching_agent,
            feasibility_agent
        ]
    )
    
    return workflow


# ============================================================================
# High-Level Interface
# ============================================================================

class AtikAIOrchestrator:
    """
    ATIK AI çoklu ajan sisteminin ana arayüzü.
    
    Agno Team ve Workflow yapılarını sarmalayarak
    kolay kullanım sağlar.
    """
    
    def __init__(self, model=None):
        """
        Args:
            model: LLM modeli (varsayılan: GPT-4o)
        """
        self.model = model or get_default_model()
        
        # Lazy initialization
        self._team: Optional[Team] = None
        self._extraction_agent: Optional[Agent] = None
        self._matching_agent: Optional[Agent] = None
        self._feasibility_agent: Optional[Agent] = None
    
    @property
    def team(self) -> Team:
        """Ana team (lazy loaded)"""
        if self._team is None:
            self._team = create_atik_team(model=self.model)
        return self._team
    
    @property
    def extraction_agent(self) -> Agent:
        """Extraction agent (lazy loaded)"""
        if self._extraction_agent is None:
            self._extraction_agent = create_extraction_agent(model=self.model)
        return self._extraction_agent
    
    @property
    def matching_agent(self) -> Agent:
        """Matching agent (lazy loaded)"""
        if self._matching_agent is None:
            self._matching_agent = create_matching_agent(model=self.model)
        return self._matching_agent
    
    @property
    def feasibility_agent(self) -> Agent:
        """Feasibility agent (lazy loaded)"""
        if self._feasibility_agent is None:
            self._feasibility_agent = create_feasibility_agent(model=self.model)
        return self._feasibility_agent
    
    def run(
        self,
        query: str,
        mode: str = AtikAITeamMode.AUTO,
        session_state: Dict = None,
        stream: bool = False
    ):
        """
        Sorguyu çalıştır.
        
        Args:
            query: Kullanıcı sorgusu
            mode: Çalışma modu (auto, full_pipeline, match_only, vb.)
            session_state: Oturum durumu
            stream: Streaming yanıt
        
        Returns:
            Yanıt veya stream iterator
        """
        if mode == AtikAITeamMode.AUTO:
            # Team kullan, Coordinator karar verir
            if stream:
                return self.team.print_response(query, stream=True)
            else:
                return self.team.run(query)
        
        elif mode == AtikAITeamMode.FULL_PIPELINE:
            # Workflow kullan
            workflow = create_full_analysis_workflow(model=self.model)
            if stream:
                return workflow.print_response(query, stream=True)
            else:
                return workflow.run(query)
        
        elif mode == AtikAITeamMode.MATCH_ONLY:
            workflow = create_quick_match_workflow(model=self.model)
            if stream:
                return workflow.print_response(query, stream=True)
            else:
                return workflow.run(query)
        
        elif mode == AtikAITeamMode.EXTRACT_ONLY:
            if stream:
                return self.extraction_agent.print_response(query, stream=True)
            else:
                return self.extraction_agent.run(query)
        
        elif mode == AtikAITeamMode.FEASIBILITY_ONLY:
            if stream:
                return self.feasibility_agent.print_response(query, stream=True)
            else:
                return self.feasibility_agent.run(query)
        
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    def print_response(self, query: str, mode: str = AtikAITeamMode.AUTO, **kwargs):
        """Yanıtı terminale yazdır"""
        return self.run(query, mode=mode, stream=True, **kwargs)
    
    # Convenience methods
    def extract_info(self, query: str, **kwargs):
        """Bilgi çıkar (ExtractionAgent)"""
        return self.extraction_agent.run(query, **kwargs)
    
    def find_matches(self, query: str, **kwargs):
        """Eşleşme bul (MatchingAgent)"""
        return self.matching_agent.run(query, **kwargs)
    
    def analyze_feasibility(self, query: str, **kwargs):
        """Fizibilite analizi (FeasibilityAgent)"""
        return self.feasibility_agent.run(query, **kwargs)
    
    def full_analysis(self, query: str, **kwargs):
        """Tam analiz (Full Pipeline)"""
        return self.run(query, mode=AtikAITeamMode.FULL_PIPELINE, **kwargs)


# ============================================================================
# Global Instance (convenience)
# ============================================================================

_orchestrator: Optional[AtikAIOrchestrator] = None


def get_orchestrator(model=None) -> AtikAIOrchestrator:
    """
    Global orchestrator instance döndür.
    
    Args:
        model: LLM modeli (sadece ilk çağrıda kullanılır)
    
    Returns:
        AtikAIOrchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AtikAIOrchestrator(model=model)
    return _orchestrator


def reset_orchestrator():
    """Global orchestrator'ı sıfırla"""
    global _orchestrator
    _orchestrator = None
