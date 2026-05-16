"""
ATIK AI - Agno Tools
Agno framework için tool fonksiyonları.

Bu dosya, Agno Agent'lar tarafından kullanılacak tool'ları tanımlar.
Agno'da tool'lar basit Python fonksiyonları olarak tanımlanır.
"""
import logging
from typing import List, Dict, Any, Optional
from agno.run import RunContext

logger = logging.getLogger(__name__)


# ============================================================================
# Embedding/Similarity Tools
# ============================================================================

def search_similar_facilities(
    facility_id: int = None,
    nace_code: str = None,
    waste_types: List[str] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Benzer tesisleri ara.
    
    Bi-Encoder embeddings kullanarak benzer tesisleri bulur.
    
    Args:
        facility_id: Referans tesis ID (varsa)
        nace_code: NACE faaliyet kodu
        waste_types: Atık tipleri listesi
        limit: Maksimum sonuç sayısı
    
    Returns:
        Benzer tesisler listesi
    """
    try:
        from ..prediction import EmbeddingManager
        
        embeddings = EmbeddingManager()
        
        if facility_id:
            results = embeddings.find_similar_to_facility(facility_id, top_k=limit)
        elif nace_code:
            results = embeddings.search_by_nace(nace_code, top_k=limit)
        else:
            results = []
        
        return results
        
    except Exception as e:
        logger.error(f"Similar facilities search error: {e}")
        return []


def search_similar_waste(
    waste_description: str,
    ewc_code: str = None,
    limit: int = 10
) -> List[Dict]:
    """
    Benzer atık tiplerini ara.
    
    Args:
        waste_description: Atık açıklaması
        ewc_code: EWC kodu (opsiyonel)
        limit: Maksimum sonuç sayısı
    
    Returns:
        Benzer atık tipleri
    """
    try:
        from ..prediction import EmbeddingManager
        
        embeddings = EmbeddingManager()
        results = embeddings.search_similar_waste(waste_description, top_k=limit)
        
        return results
        
    except Exception as e:
        logger.error(f"Similar waste search error: {e}")
        return []


# ============================================================================
# Matching Tools (Matching Agent)
# ============================================================================

def find_waste_matches(
    source_facility_id: int,
    waste_type_id: int,
    max_distance_km: float = 100.0,
    min_score: float = 0.5,
    limit: int = 20
) -> List[Dict]:
    """
    Atık için potansiyel alıcı tesisleri bul.
    
    3 katmanlı filtreleme uygular:
    1. Teknik uyumluluk (NACE-EWC kuralları)
    2. Zamansal uyum (mevsimsellik, üretim dönemleri)
    3. Coğrafi yakınlık
    
    Args:
        source_facility_id: Kaynak tesis ID
        waste_type_id: Atık tip ID
        max_distance_km: Maksimum mesafe (km)
        min_score: Minimum eşleşme skoru (0-1)
        limit: Maksimum sonuç sayısı
    
    Returns:
        Potansiyel eşleşmeler listesi, skor ile sıralı
    """
    try:
        from ..matching import MatchingEngine
        
        engine = MatchingEngine()
        matches = engine.find_matches(
            source_facility_id=source_facility_id,
            waste_type_id=waste_type_id,
            max_distance=max_distance_km,
            min_score=min_score,
            limit=limit
        )
        
        return [
            {
                "receiver_facility_id": m.receiver_facility_id,
                "receiver_name": m.receiver_name,
                "distance_km": m.distance_km,
                "technical_score": m.technical_score,
                "temporal_score": m.temporal_score,
                "geographic_score": m.geographic_score,
                "total_score": m.total_score,
                "match_reason": m.reason
            }
            for m in matches
        ]
        
    except Exception as e:
        logger.error(f"Find matches error: {e}")
        return []


def check_technical_compatibility(
    source_nace: str,
    source_ewc: str,
    receiver_nace: str
) -> Dict:
    """
    Teknik uyumluluk kontrolü yap.
    
    NACE-EWC kurallarına göre atık transferinin teknik olarak
    mümkün olup olmadığını kontrol eder.
    
    Args:
        source_nace: Kaynak tesis NACE kodu
        source_ewc: Atık EWC kodu
        receiver_nace: Alıcı tesis NACE kodu
    
    Returns:
        Uyumluluk sonucu ve detayları
    """
    try:
        from ..matching import TechnicalMatcher
        
        matcher = TechnicalMatcher()
        result = matcher.check_compatibility(
            source_nace=source_nace,
            source_ewc=source_ewc,
            receiver_nace=receiver_nace
        )
        
        return {
            "is_compatible": result.is_compatible,
            "compatibility_score": result.score,
            "matching_rules": result.rules_matched,
            "reason": result.reason
        }
        
    except Exception as e:
        logger.error(f"Technical compatibility check error: {e}")
        return {"is_compatible": False, "error": str(e)}


def check_temporal_compatibility(
    source_facility_id: int,
    receiver_facility_id: int,
    waste_type_id: int
) -> Dict:
    """
    Zamansal uyumluluk kontrolü yap.
    
    Mevsimsel üretim/tüketim paternlerini analiz eder.
    
    Args:
        source_facility_id: Kaynak tesis ID
        receiver_facility_id: Alıcı tesis ID
        waste_type_id: Atık tip ID
    
    Returns:
        Zamansal uyumluluk skoru ve analiz
    """
    try:
        from ..matching import TemporalMatcher
        
        matcher = TemporalMatcher()
        result = matcher.analyze_sync(
            source_id=source_facility_id,
            receiver_id=receiver_facility_id,
            waste_type_id=waste_type_id
        )
        
        return {
            "sync_score": result.sync_score,
            "best_months": result.best_months,
            "source_pattern": result.source_pattern,
            "receiver_pattern": result.receiver_pattern,
            "recommendation": result.recommendation
        }
        
    except Exception as e:
        logger.error(f"Temporal compatibility check error: {e}")
        return {"sync_score": 0.5, "error": str(e)}


# ============================================================================
# Feasibility Tools (Feasibility Agent)
# ============================================================================

def analyze_economic_feasibility(
    source_facility_id: int,
    receiver_facility_id: int,
    waste_type_id: int,
    waste_amount_tons: float,
    distance_km: float = None
) -> Dict:
    """
    Ekonomik fizibilite analizi yap (SWAN modeli).
    
    Break-even fiyatları ve kar marjlarını hesaplar.
    
    Args:
        source_facility_id: Kaynak tesis ID
        receiver_facility_id: Alıcı tesis ID
        waste_type_id: Atık tip ID
        waste_amount_tons: Atık miktarı (ton)
        distance_km: Mesafe (biliniyorsa)
    
    Returns:
        Detaylı ekonomik analiz sonucu
    """
    try:
        from ..economics import FeasibilityAnalyzer
        
        analyzer = FeasibilityAnalyzer()
        result = analyzer.analyze(
            source_facility_id=source_facility_id,
            receiver_facility_id=receiver_facility_id,
            waste_type_id=waste_type_id,
            waste_amount=waste_amount_tons,
            distance=distance_km
        )
        
        return {
            "is_feasible": result.is_feasible,
            "source_profit": result.source_profit,
            "receiver_profit": result.receiver_profit,
            "price_wbes": result.price_wbes,  # Source break-even price
            "price_wber": result.price_wber,  # Receiver break-even price
            "suggested_price": result.suggested_price,
            "transport_cost": result.transport_cost,
            "total_logistics_cost": result.total_logistics_cost,
            "recommendation": result.recommendation,
            "risk_factors": result.risk_factors
        }
        
    except Exception as e:
        logger.error(f"Feasibility analysis error: {e}")
        return {"is_feasible": False, "error": str(e)}


def calculate_transport_cost(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    waste_amount_tons: float,
    vehicle_capacity_tons: float = 20.0
) -> Dict:
    """
    Nakliye maliyeti hesapla.
    
    TC = (W/C) × FC_T × P_F × D formülünü kullanır.
    
    Args:
        origin_lat: Başlangıç enlemi
        origin_lon: Başlangıç boylamı
        dest_lat: Varış enlemi
        dest_lon: Varış boylamı
        waste_amount_tons: Atık miktarı (ton)
        vehicle_capacity_tons: Araç kapasitesi (ton)
    
    Returns:
        Nakliye maliyet detayları
    """
    try:
        from ..economics import LogisticsCalculator
        from ..distance import DistanceCalculator
        
        # Mesafe hesapla
        dist_calc = DistanceCalculator()
        distance = dist_calc.calculate(origin_lat, origin_lon, dest_lat, dest_lon)
        
        # Maliyet hesapla
        logistics = LogisticsCalculator()
        cost = logistics.calculate_transport_cost(
            waste_amount=waste_amount_tons,
            distance_km=distance.distance_km,
            vehicle_capacity=vehicle_capacity_tons
        )
        
        return {
            "distance_km": distance.distance_km,
            "duration_minutes": distance.duration_minutes,
            "transport_cost": cost.total_cost,
            "cost_per_ton": cost.cost_per_ton,
            "number_of_trips": cost.trips_needed,
            "fuel_cost": cost.fuel_cost,
            "driver_cost": cost.driver_cost
        }
        
    except Exception as e:
        logger.error(f"Transport cost calculation error: {e}")
        return {"error": str(e)}


def calculate_pricing(
    waste_type_id: int,
    waste_amount_tons: float,
    transport_cost: float,
    processing_cost: float = None
) -> Dict:
    """
    Atık fiyatlandırması hesapla.
    
    SWAN modelinin P_WBES ve P_WBER formüllerini kullanır.
    
    Args:
        waste_type_id: Atık tip ID
        waste_amount_tons: Atık miktarı
        transport_cost: Toplam nakliye maliyeti
        processing_cost: İşleme maliyeti (biliniyorsa)
    
    Returns:
        Fiyat önerileri ve break-even noktaları
    """
    try:
        from ..economics import PricingEngine
        
        engine = PricingEngine()
        result = engine.calculate_prices(
            waste_type_id=waste_type_id,
            waste_amount=waste_amount_tons,
            transport_cost=transport_cost,
            processing_cost=processing_cost
        )
        
        return {
            "price_wbes": result.price_wbes,  # Min price for source to be profitable
            "price_wber": result.price_wber,  # Max price for receiver to be profitable
            "suggested_price": result.suggested_price,
            "is_viable": result.is_viable,
            "source_margin": result.source_margin,
            "receiver_margin": result.receiver_margin,
            "market_reference_price": result.market_price
        }
        
    except Exception as e:
        logger.error(f"Pricing calculation error: {e}")
        return {"error": str(e)}


# ============================================================================
# Database/Facility Tools
# ============================================================================

def get_facility_info(facility_id: int) -> Dict:
    """
    Tesis bilgilerini getir.
    
    Args:
        facility_id: Tesis ID
    
    Returns:
        Tesis detayları
    """
    try:
        from ..core import DatabaseManager
        from ..core.models import Facility
        
        db = DatabaseManager()
        with db.session() as session:
            facility = session.query(Facility).get(facility_id)
            if facility:
                return {
                    "id": facility.id,
                    "name": facility.name,
                    "nace_code": facility.nace_code,
                    "latitude": facility.latitude,
                    "longitude": facility.longitude,
                    "address": facility.address,
                    "city": facility.city,
                    "capacity_tons": facility.capacity
                }
        return {"error": "Facility not found"}
        
    except Exception as e:
        logger.error(f"Get facility info error: {e}")
        return {"error": str(e)}


def get_waste_type_info(waste_type_id: int) -> Dict:
    """
    Atık tipi bilgilerini getir.
    
    Args:
        waste_type_id: Atık tip ID
    
    Returns:
        Atık tipi detayları
    """
    try:
        from ..core import DatabaseManager
        from ..core.models import WasteType
        
        db = DatabaseManager()
        with db.session() as session:
            waste = session.query(WasteType).get(waste_type_id)
            if waste:
                return {
                    "id": waste.id,
                    "name": waste.name,
                    "ewc_code": waste.ewc_code,
                    "category": waste.category,
                    "hazardous": waste.is_hazardous,
                    "recyclable": waste.is_recyclable,
                    "unit": waste.unit
                }
        return {"error": "Waste type not found"}
        
    except Exception as e:
        logger.error(f"Get waste type info error: {e}")
        return {"error": str(e)}


def list_facilities_by_nace(nace_code: str, limit: int = 50) -> List[Dict]:
    """
    NACE koduna göre tesisleri listele.
    
    Args:
        nace_code: NACE faaliyet kodu (örn: "38.11" - tehlikesiz atık toplama)
        limit: Maksimum sonuç sayısı
    
    Returns:
        Tesis listesi
    """
    try:
        from ..core import DatabaseManager
        from ..core.models import Facility
        
        db = DatabaseManager()
        with db.session() as session:
            facilities = session.query(Facility).filter(
                Facility.nace_code.like(f"{nace_code}%")
            ).limit(limit).all()
            
            return [
                {
                    "id": f.id,
                    "name": f.name,
                    "nace_code": f.nace_code,
                    "city": f.city
                }
                for f in facilities
            ]
        
    except Exception as e:
        logger.error(f"List facilities error: {e}")
        return []


# ============================================================================
# Distance Tools
# ============================================================================

def calculate_distance(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    use_road_network: bool = True
) -> Dict:
    """
    İki nokta arasındaki mesafeyi hesapla.
    
    Args:
        origin_lat: Başlangıç enlemi
        origin_lon: Başlangıç boylamı
        dest_lat: Varış enlemi
        dest_lon: Varış boylamı
        use_road_network: Yol ağı kullanılsın mı (True) yoksa kuş uçuşu mu (False)
    
    Returns:
        Mesafe ve süre bilgisi
    """
    try:
        from ..distance import DistanceCalculator
        
        calc = DistanceCalculator()
        
        if use_road_network:
            result = calc.calculate(origin_lat, origin_lon, dest_lat, dest_lon)
        else:
            result = calc.calculate_haversine(origin_lat, origin_lon, dest_lat, dest_lon)
        
        return {
            "distance_km": result.distance_km,
            "duration_minutes": result.duration_minutes,
            "source": result.source  # "osmnx", "ors", "haversine"
        }
        
    except Exception as e:
        logger.error(f"Distance calculation error: {e}")
        return {"error": str(e)}


# ============================================================================
# Agno RunContext aware tools
# ============================================================================

def get_session_context(run_context: RunContext) -> Dict:
    """
    Mevcut oturum bağlamını getir.
    
    Bu tool, Agno'nun session_state'inden ATIK AI durumunu okur.
    
    Args:
        run_context: Agno run context (otomatik inject edilir)
    
    Returns:
        Oturum state bilgisi
    """
    state = run_context.session_state or {}
    return {
        "current_facility_id": state.get("current_facility_id"),
        "current_waste_type_id": state.get("current_waste_type_id"),
        "max_distance_km": state.get("max_distance_km", 100.0),
        "last_matches_count": len(state.get("last_matches", []))
    }


def update_session_state(
    run_context: RunContext,
    key: str,
    value: Any
) -> str:
    """
    Oturum durumunu güncelle.
    
    Args:
        run_context: Agno run context
        key: Güncellenecek anahtar
        value: Yeni değer
    
    Returns:
        Onay mesajı
    """
    if not run_context.session_state:
        run_context.session_state = {}
    
    run_context.session_state[key] = value
    return f"Session state updated: {key} = {value}"


# ============================================================================
# Tool Collections (for different agent roles)
# ============================================================================

# Extraction Agent tools
EXTRACTION_TOOLS = [
    search_similar_facilities,
    search_similar_waste,
    get_facility_info,
    get_waste_type_info,
]

# Matching Agent tools
MATCHING_TOOLS = [
    find_waste_matches,
    check_technical_compatibility,
    check_temporal_compatibility,
    calculate_distance,
    list_facilities_by_nace,
    get_facility_info,
]

# Feasibility Agent tools
FEASIBILITY_TOOLS = [
    analyze_economic_feasibility,
    calculate_transport_cost,
    calculate_pricing,
    calculate_distance,
    get_facility_info,
    get_waste_type_info,
]

# All tools for coordinator
ALL_TOOLS = list(set(
    EXTRACTION_TOOLS + MATCHING_TOOLS + FEASIBILITY_TOOLS + 
    [get_session_context, update_session_state]
))
