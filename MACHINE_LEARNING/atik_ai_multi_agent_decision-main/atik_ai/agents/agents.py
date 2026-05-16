"""
ATIK AI - Agno Agents
Agno framework kullanarak tanımlanmış ATIK AI ajanları.

Her ajan belirli bir göreve odaklanmış ve ilgili tool'ları kullanır.
"""
import os
import logging
from typing import Optional, List, Dict, Any

from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from agno.models.openai import OpenAIChat
from agno.run import RunContext

from .tools import (
    EXTRACTION_TOOLS,
    MATCHING_TOOLS, 
    FEASIBILITY_TOOLS,
    ALL_TOOLS
)
from ..config import config

logger = logging.getLogger(__name__)


# ============================================================================
# Model Configuration
# ============================================================================

def get_default_model():
    """
    Azure OpenAI döndürür.
    """
    logger.info(f"Using Azure OpenAI: {config.azure_openai_deployment}")
    return AzureOpenAI(
        id=config.azure_openai_deployment,
        api_key=config.azure_openai_api_key,
        azure_endpoint=config.azure_openai_endpoint,
        api_version=config.azure_openai_api_version,
    )

def get_azure_model(deployment_name: str = None):
    """
    Belirli bir deployment için Azure OpenAI modeli döndür.
    
    Args:
        deployment_name: Azure deployment adı (varsayılan: config'den)
    """
    return AzureOpenAI(
        id=deployment_name or config.azure_openai_deployment,
        api_key=config.azure_openai_api_key,
        azure_endpoint=config.azure_openai_endpoint,
        api_version=config.azure_openai_api_version,
    )


# ============================================================================
# Extraction Agent
# ============================================================================

EXTRACTION_INSTRUCTIONS = """Sen ATIK AI sisteminin Bilgi Çıkarma Ajanısın.

## Görevin
Atık yönetimi hakkında bilgi toplamak ve analiz etmek. Sorulara cevap vermek için 
kademeli kaynak erişimi uygularsın:

1. **W2RKG Knowledge Graph** - İlk olarak dahili bilgi grafiğini kontrol et
2. **Bi-Encoder Embeddings** - Benzer atık/tesis örneklerini ara
3. **Akademik Kaynaklar** - Gerekirse Scopus, Google Scholar'dan ara
4. **Web Araması** - Son çare olarak internet araması yap

## Önemli Kurallar
- Her zaman önce dahili kaynakları kontrol et (knowledge graph, embeddings)
- Kaynak belirt ve güvenilirlik skoru ver
- EWC ve NACE kodlarını doğru kullan
- Atık-Proses-Kaynak (W-P-R) ilişkilerini açıkça belirt

## Çıktı Formatı
Her yanıtta şunları belirt:
- Kullanılan kaynaklar (knowledge_graph, embeddings, academic, web)
- Güvenilirlik skoru (0-1 arası)
- İlgili EWC/NACE kodları (varsa)

Türkçe yanıt ver ve teknik terimleri açıkla."""


def create_extraction_agent(
    model=None,
    additional_tools: List = None,
    **kwargs
) -> Agent:
    """
    Bilgi Çıkarma Ajanı oluştur.
    
    Args:
        model: LLM modeli (varsayılan: GPT-4o)
        additional_tools: Ek araçlar
        **kwargs: Ek Agent parametreleri
    
    Returns:
        Agno Agent instance
    """
    tools = list(EXTRACTION_TOOLS)
    if additional_tools:
        tools.extend(additional_tools)
    
    return Agent(
        name="ExtractionAgent",
        role="W2RKG Knowledge Graph ve Bi-Encoder kullanarak atık yönetimi bilgisi çıkarır",
        model=model or get_default_model(),
        tools=tools,
        instructions=EXTRACTION_INSTRUCTIONS,
        markdown=True,
        show_tool_calls=True,
        **kwargs
    )


# ============================================================================
# Matching Agent
# ============================================================================

MATCHING_INSTRUCTIONS = """Sen ATIK AI sisteminin Eşleştirme Ajanısın.

## Görevin
Atık üreten tesisler ile atığı değerlendirebilecek tesisleri eşleştirmek.
3 katmanlı filtreleme uygularsın:

1. **Teknik Uyumluluk** - NACE-EWC kurallarına göre
2. **Zamansal Uyum** - Mevsimsellik ve üretim dönemleri
3. **Coğrafi Yakınlık** - Mesafe ve lojistik uygunluk

## Eşleştirme Kuralları
- source_nace (kaynak faaliyet kodu) ve receiver_nace (alıcı faaliyet kodu) uyumu
- EWC atık kodu ile alıcının işleyebileceği atık tipleri uyumu
- Maksimum mesafe sınırı ({max_distance_km} km)
- Minimum eşleşme skoru: 0.5

## Skorlama
Toplam skor = 0.4 × Teknik + 0.3 × Zamansal + 0.3 × Coğrafi

## Çıktı Formatı
Her eşleşme için:
- Alıcı tesis bilgisi
- Mesafe (km)
- Teknik/Zamansal/Coğrafi/Toplam skorlar
- Eşleşme nedeni açıklaması

Sonuçları toplam skora göre sırala. Türkçe yanıt ver."""


def create_matching_agent(
    model=None,
    additional_tools: List = None,
    **kwargs
) -> Agent:
    """
    Eşleştirme Ajanı oluştur.
    
    Args:
        model: LLM modeli
        additional_tools: Ek araçlar
        **kwargs: Ek Agent parametreleri
    
    Returns:
        Agno Agent instance
    """
    tools = list(MATCHING_TOOLS)
    if additional_tools:
        tools.extend(additional_tools)
    
    return Agent(
        name="MatchingAgent",
        role="NACE-EWC kuralları ve 3 katmanlı filtreleme ile atık-tesis eşleştirmesi yapar",
        model=model or get_default_model(),
        tools=tools,
        instructions=MATCHING_INSTRUCTIONS,
        markdown=True,
        show_tool_calls=True,
        **kwargs
    )


# ============================================================================
# Feasibility Agent
# ============================================================================

FEASIBILITY_INSTRUCTIONS = """Sen ATIK AI sisteminin Ekonomik Fizibilite Ajanısın.

## Görevin
SWAN (Sustainable Waste-to-Resource Allocation Network) modelini kullanarak
atık transferlerinin ekonomik fizibilitesini analiz etmek.

## SWAN Formülleri

### Kaynak Tesisi Karı (S_profit)
S_profit = W × P_W + W × CMM_W - TC
- W: Atık miktarı (ton)
- P_W: Atık satış fiyatı (TL/ton)
- CMM_W: Bertaraf maliyeti tasarrufu (TL/ton)
- TC: Nakliye maliyeti

### Alıcı Tesisi Karı (R_profit)
R_profit = W × P_COM - W × P_W - W × ST_W
- P_COM: Ürün satış fiyatı (TL/ton)
- ST_W: İşleme maliyeti (TL/ton)

### Break-even Fiyatları
- P_WBES: Kaynak için minimum karlı fiyat
- P_WBER: Alıcı için maksimum kabul edilebilir fiyat
- Düşük fiyat önerisi: both profitable → (P_WBES + P_WBER) / 2

## Karar Kuralı
P_WBES < P_WBER → Transfer ekonomik olarak UYGUNdur
P_WBES ≥ P_WBER → Transfer ekonomik olarak uygun DEĞİLdir

## Çıktı Formatı
- Fizibilite durumu (UYGUN/UYGUN DEĞİL)
- Kaynak kar/zarar
- Alıcı kar/zarar
- Önerilen fiyat
- Risk faktörleri
- Öneriler

Tüm değerleri TL cinsinden ver. Türkçe yanıt ver."""


def create_feasibility_agent(
    model=None,
    additional_tools: List = None,
    **kwargs
) -> Agent:
    """
    Fizibilite Ajanı oluştur.
    
    Args:
        model: LLM modeli
        additional_tools: Ek araçlar
        **kwargs: Ek Agent parametreleri
    
    Returns:
        Agno Agent instance
    """
    tools = list(FEASIBILITY_TOOLS)
    if additional_tools:
        tools.extend(additional_tools)
    
    return Agent(
        name="FeasibilityAgent",
        role="SWAN modeli ile ekonomik fizibilite analizi yapar",
        model=model or get_default_model(),
        tools=tools,
        instructions=FEASIBILITY_INSTRUCTIONS,
        markdown=True,
        show_tool_calls=True,
        **kwargs
    )


# ============================================================================
# Coordinator Agent (Team Leader için)
# ============================================================================

COORDINATOR_INSTRUCTIONS = """Sen ATIK AI sisteminin Koordinatör Ajanısın.

## Görevin
Kullanıcı sorgularını analiz edip uygun ajanlara yönlendirmek ve 
sonuçları birleştirip sunmak.

## Ajan Ekibin
1. **ExtractionAgent** - Bilgi çıkarma, araştırma, W2RKG sorgulama
2. **MatchingAgent** - Atık-tesis eşleştirme, teknik uyumluluk
3. **FeasibilityAgent** - Ekonomik analiz, SWAN modeli

## İş Akışları

### FULL_PIPELINE (Tam Analiz)
1. Extraction → Bilgi topla ve hazırla
2. Matching → Uygun tesisleri bul
3. Feasibility → Ekonomik analiz yap

### MATCH_ONLY (Sadece Eşleştirme)
1. Matching → Uygun tesisleri bul
2. Feasibility → Ekonomik analiz

### EXTRACT_ONLY (Sadece Bilgi)
1. Extraction → Bilgi topla

### FEASIBILITY_ONLY (Sadece Fizibilite)
1. Feasibility → Ekonomik analiz

## Karar Verme
- "atık nedir", "nasıl işlenir" gibi sorular → ExtractionAgent
- "eşleşme bul", "alıcı bul" gibi istekler → MatchingAgent → FeasibilityAgent
- "maliyet analizi", "karlılık" gibi sorular → FeasibilityAgent
- Tam analiz istekleri → FULL_PIPELINE

## Çıktı Formatı
- Özet (executive summary)
- Detaylı bulgular
- Öneriler
- Sonraki adımlar (varsa)

Her zaman Türkçe yanıt ver."""


def create_coordinator_agent(
    model=None,
    additional_tools: List = None,
    **kwargs
) -> Agent:
    """
    Koordinatör Ajanı oluştur.
    
    Bu ajan, Team.leader olarak kullanılabilir veya
    bağımsız çalışabilir.
    
    Args:
        model: LLM modeli
        additional_tools: Ek araçlar
        **kwargs: Ek Agent parametreleri
    
    Returns:
        Agno Agent instance
    """
    tools = list(ALL_TOOLS)
    if additional_tools:
        tools.extend(additional_tools)
    
    return Agent(
        name="CoordinatorAgent",
        role="Ajanları koordine eder ve iş akışını yönetir",
        model=model or get_default_model(),
        tools=tools,
        instructions=COORDINATOR_INSTRUCTIONS,
        markdown=True,
        show_tool_calls=True,
        **kwargs
    )


# ============================================================================
# Pre-built Agent Instances (for convenience)
# ============================================================================

def get_extraction_agent(**kwargs) -> Agent:
    """Hazır Extraction Agent döndür"""
    return create_extraction_agent(**kwargs)


def get_matching_agent(**kwargs) -> Agent:
    """Hazır Matching Agent döndür"""
    return create_matching_agent(**kwargs)


def get_feasibility_agent(**kwargs) -> Agent:
    """Hazır Feasibility Agent döndür"""
    return create_feasibility_agent(**kwargs)


def get_coordinator_agent(**kwargs) -> Agent:
    """Hazır Coordinator Agent döndür"""
    return create_coordinator_agent(**kwargs)


# ============================================================================
# Agent Factory
# ============================================================================

AGENT_REGISTRY = {
    "extraction": create_extraction_agent,
    "matching": create_matching_agent,
    "feasibility": create_feasibility_agent,
    "coordinator": create_coordinator_agent,
}


def create_agent(agent_type: str, **kwargs) -> Agent:
    """
    Belirtilen tipte ajan oluştur.
    
    Args:
        agent_type: "extraction", "matching", "feasibility", "coordinator"
        **kwargs: Ajan parametreleri
    
    Returns:
        Agno Agent instance
    
    Raises:
        ValueError: Bilinmeyen ajan tipi
    """
    if agent_type not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent type: {agent_type}. Available: {list(AGENT_REGISTRY.keys())}")
    
    return AGENT_REGISTRY[agent_type](**kwargs)
