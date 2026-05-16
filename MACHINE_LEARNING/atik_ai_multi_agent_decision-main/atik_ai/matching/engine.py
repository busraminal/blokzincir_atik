"""
ATIK AI - Matching Engine
3 Katmanlı Filtreleme Algoritması

Katman 1: Teknik Uyumluluk (NACE-EWC)
Katman 2: Zamansal Uyumluluk
Katman 3: Coğrafi Uyumluluk (Mesafe)

Her katman bir öncekinin çıktısını filtreler.
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import date

from .technical import TechnicalMatcher, TechnicalRule
from .temporal import TemporalMatcher, Season
from ..distance import DistanceCalculator, DistanceCache
from ..economics import FeasibilityAnalyzer, MatchInput
from ..core.exceptions import MatchingError
from ..config import config

logger = logging.getLogger(__name__)


@dataclass
class MatchCandidate:
    """Eşleşme adayı"""
    source_id: int
    receiver_id: int
    waste_type_id: int
    ewc_code: str
    
    # Skorlar
    technical_score: float = 0.0
    temporal_score: float = 0.0
    distance_score: float = 0.0
    overall_score: float = 0.0
    
    # Detaylar
    distance_km: float = 0.0
    matching_rule: Optional[TechnicalRule] = None
    temporal_details: Dict = field(default_factory=dict)
    
    def calculate_overall_score(
        self,
        tech_weight: float = 0.4,
        temp_weight: float = 0.2,
        dist_weight: float = 0.4
    ):
        """Genel skor hesapla"""
        self.overall_score = (
            self.technical_score * tech_weight +
            self.temporal_score * temp_weight +
            self.distance_score * dist_weight
        )
        return self.overall_score


@dataclass
class MatchResult:
    """Eşleşme sonucu"""
    source_id: int
    receiver_id: int
    waste_type_id: int
    ewc_code: str
    
    # Skorlar
    overall_score: float
    technical_score: float
    temporal_score: float
    distance_score: float
    
    # Mesafe
    distance_km: float
    
    # Ekonomik (opsiyonel)
    is_economically_feasible: bool = None
    feasibility_result: Dict = None
    
    # Meta
    rank: int = 0
    match_quality: str = "unknown"
    
    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "receiver_id": self.receiver_id,
            "waste_type_id": self.waste_type_id,
            "ewc_code": self.ewc_code,
            "overall_score": self.overall_score,
            "technical_score": self.technical_score,
            "temporal_score": self.temporal_score,
            "distance_score": self.distance_score,
            "distance_km": self.distance_km,
            "is_economically_feasible": self.is_economically_feasible,
            "rank": self.rank,
            "match_quality": self.match_quality
        }


class MatchingEngine:
    """
    Eşleştirme Motoru
    
    3 katmanlı filtreleme:
    1. Teknik filtre (NACE-EWC kuralları)
    2. Zamansal filtre (mevsimsel uyum)
    3. Coğrafi filtre (mesafe > 200km elensin)
    
    Her katman skoru 0-1 arası normalize edilir.
    Genel skor = weighted average
    """
    
    def __init__(
        self,
        technical_matcher: TechnicalMatcher = None,
        temporal_matcher: TemporalMatcher = None,
        distance_calculator: DistanceCalculator = None,
        feasibility_analyzer: FeasibilityAnalyzer = None,
        max_distance_km: float = None,
        min_technical_score: float = None,
        min_overall_score: float = None
    ):
        self.technical = technical_matcher or TechnicalMatcher()
        self.temporal = temporal_matcher or TemporalMatcher()
        
        if distance_calculator:
            self._distance = distance_calculator
        else:
            self._distance = None
        
        self.feasibility = feasibility_analyzer
        
        # Eşikler
        self.max_distance_km = max_distance_km or config.matching.max_distance_km
        self.min_technical_score = min_technical_score or config.matching.min_technical_score
        self.min_overall_score = min_overall_score or config.matching.min_overall_score
        
        # Ağırlıklar
        self.tech_weight = 0.4
        self.temp_weight = 0.2
        self.dist_weight = 0.4
    
    @property
    def distance_calculator(self) -> DistanceCalculator:
        """Lazy distance calculator"""
        if self._distance is None:
            cache = DistanceCache()
            from ..distance.calculator import DistanceStrategy
            self._distance = DistanceCalculator(
                strategy=DistanceStrategy.HAVERSINE,
                cache=cache
            )
        return self._distance
    
    def set_weights(
        self,
        technical: float = 0.4,
        temporal: float = 0.2,
        distance: float = 0.4
    ):
        """Skor ağırlıklarını ayarla"""
        total = technical + temporal + distance
        self.tech_weight = technical / total
        self.temp_weight = temporal / total
        self.dist_weight = distance / total
    
    # =========================================================================
    # KATMAN 1: TEKNİK FİLTRE
    # =========================================================================
    
    def technical_filter(
        self,
        source_ewc: str,
        receivers: List[Dict]  # [{id, nace, ...}]
    ) -> List[Tuple[Dict, float, TechnicalRule]]:
        """
        Teknik uyumluluk filtresi
        
        Args:
            source_ewc: Kaynak EWC kodu
            receivers: Alıcı listesi
            
        Returns:
            [(receiver, score, rule), ...]
        """
        passed = []
        
        for receiver in receivers:
            nace = receiver.get("nace", "")
            is_compat, score, rule = self.technical.check_compatibility(source_ewc, nace)
            
            if is_compat and score >= self.min_technical_score:
                passed.append((receiver, score, rule))
        
        # Skora göre sırala
        passed.sort(key=lambda x: x[1], reverse=True)
        
        return passed
    
    # =========================================================================
    # KATMAN 2: ZAMANSAL FİLTRE
    # =========================================================================
    
    def temporal_filter(
        self,
        source_nace: str,
        receiver_nace: str,
        ewc: str,
        target_date: date = None
    ) -> Tuple[float, Dict]:
        """
        Zamansal uyumluluk filtresi
        
        Returns:
            (score, details)
        """
        result = self.temporal.calculate_temporal_score(
            source_nace, receiver_nace, ewc, target_date
        )
        
        return result["temporal_score"], result
    
    # =========================================================================
    # KATMAN 3: COĞRAFİ FİLTRE
    # =========================================================================
    
    def geographic_filter(
        self,
        source_coords: Tuple[float, float],
        receiver_coords: Tuple[float, float]
    ) -> Tuple[bool, float, float]:
        """
        Coğrafi uyumluluk filtresi
        
        Returns:
            (passed, distance_km, score)
        """
        # Mesafe hesapla
        result = self.distance_calculator.calculate(source_coords, receiver_coords)
        distance = result.distance_km
        
        # Maksimum mesafe kontrolü
        if distance > self.max_distance_km:
            return False, distance, 0.0
        
        # Mesafe skoru (yakın = yüksek skor)
        # 0 km = 1.0, max_distance = 0.0
        score = 1.0 - (distance / self.max_distance_km)
        score = max(0, min(1, score))
        
        return True, distance, score
    
    # =========================================================================
    # ANA EŞLEŞME
    # =========================================================================
    
    def find_matches(
        self,
        source: Dict,          # {id, nace, ewc_codes, coords, waste_quantity, ...}
        receivers: List[Dict], # [{id, nace, coords, ...}, ...]
        target_date: date = None,
        max_results: int = 10,
        include_economic: bool = False
    ) -> List[MatchResult]:
        """
        3 katmanlı eşleşme bulma
        
        Args:
            source: Kaynak tesis bilgisi
            receivers: Potansiyel alıcılar
            target_date: Hedef tarih
            max_results: Maksimum sonuç sayısı
            include_economic: Ekonomik analiz dahil et
            
        Returns:
            Sıralanmış eşleşme listesi
        """
        source_coords = source.get("coords")
        source_nace = source.get("nace", "")
        ewc_codes = source.get("ewc_codes", [])
        
        if not source_coords:
            raise MatchingError("Kaynak koordinatları eksik")
        
        results = []
        
        for ewc in ewc_codes:
            # KATMAN 1: Teknik Filtre
            technical_passed = self.technical_filter(ewc, receivers)
            
            for receiver, tech_score, rule in technical_passed:
                receiver_coords = receiver.get("coords")
                receiver_nace = receiver.get("nace", "")
                
                if not receiver_coords:
                    continue
                
                # KATMAN 3: Coğrafi Filtre (önce çünkü hızlı)
                geo_passed, distance, dist_score = self.geographic_filter(
                    source_coords, receiver_coords
                )
                
                if not geo_passed:
                    continue
                
                # KATMAN 2: Zamansal Filtre
                temp_score, temp_details = self.temporal_filter(
                    source_nace, receiver_nace, ewc, target_date
                )
                
                # Genel skor
                overall = (
                    tech_score * self.tech_weight +
                    temp_score * self.temp_weight +
                    dist_score * self.dist_weight
                )
                
                if overall < self.min_overall_score:
                    continue
                
                # Eşleşme oluştur
                match = MatchResult(
                    source_id=source["id"],
                    receiver_id=receiver["id"],
                    waste_type_id=receiver.get("waste_type_id", 0),
                    ewc_code=ewc,
                    overall_score=round(overall, 4),
                    technical_score=round(tech_score, 4),
                    temporal_score=round(temp_score, 4),
                    distance_score=round(dist_score, 4),
                    distance_km=round(distance, 2)
                )
                
                # Ekonomik analiz
                if include_economic and self.feasibility:
                    match = self._add_economic_analysis(source, receiver, match)
                
                # Kalite etiketi
                match.match_quality = self._get_quality_label(overall)
                
                results.append(match)
        
        # Sırala
        results.sort(key=lambda x: x.overall_score, reverse=True)
        
        # Rank ekle
        for i, result in enumerate(results):
            result.rank = i + 1
        
        return results[:max_results]
    
    def _add_economic_analysis(
        self,
        source: Dict,
        receiver: Dict,
        match: MatchResult
    ) -> MatchResult:
        """Ekonomik analiz ekle"""
        try:
            match_input = MatchInput(
                source_facility_id=source["id"],
                receiver_facility_id=receiver["id"],
                waste_type_id=match.waste_type_id,
                waste_quantity_ton=source.get("waste_quantity", 1),
                source_coords=source["coords"],
                receiver_coords=receiver["coords"],
                disposal_savings=source.get("disposal_savings", 50),
                commercial_price=receiver.get("commercial_price", 100)
            )
            
            result = self.feasibility.analyze(match_input)
            match.is_economically_feasible = result.is_feasible
            match.feasibility_result = result.to_dict()
            
        except Exception as e:
            logger.warning(f"Ekonomik analiz hatası: {e}")
            match.is_economically_feasible = None
        
        return match
    
    def _get_quality_label(self, score: float) -> str:
        """Skor bazlı kalite etiketi"""
        if score >= 0.8:
            return "excellent"
        elif score >= 0.6:
            return "good"
        elif score >= 0.4:
            return "moderate"
        else:
            return "weak"
    
    # =========================================================================
    # TOPLU EŞLEŞME
    # =========================================================================
    
    def batch_match(
        self,
        sources: List[Dict],
        receivers: List[Dict],
        target_date: date = None,
        top_n_per_source: int = 5
    ) -> Dict[int, List[MatchResult]]:
        """
        Toplu eşleşme
        
        Args:
            sources: Kaynak tesisler
            receivers: Alıcı tesisler
            top_n_per_source: Her kaynak için en iyi N eşleşme
            
        Returns:
            {source_id: [matches], ...}
        """
        all_matches = {}
        
        for source in sources:
            try:
                matches = self.find_matches(
                    source, receivers,
                    target_date=target_date,
                    max_results=top_n_per_source
                )
                all_matches[source["id"]] = matches
            except Exception as e:
                logger.warning(f"Eşleşme hatası (source: {source['id']}): {e}")
                all_matches[source["id"]] = []
        
        return all_matches
    
    def find_best_match(
        self,
        source: Dict,
        receivers: List[Dict],
        target_date: date = None
    ) -> Optional[MatchResult]:
        """En iyi eşleşmeyi bul"""
        matches = self.find_matches(
            source, receivers,
            target_date=target_date,
            max_results=1
        )
        return matches[0] if matches else None
    
    # =========================================================================
    # ANALİZ
    # =========================================================================
    
    def analyze_match_distribution(
        self,
        matches: List[MatchResult]
    ) -> Dict:
        """Eşleşme dağılım analizi"""
        if not matches:
            return {"total": 0}
        
        scores = [m.overall_score for m in matches]
        distances = [m.distance_km for m in matches]
        
        quality_counts = {
            "excellent": sum(1 for m in matches if m.match_quality == "excellent"),
            "good": sum(1 for m in matches if m.match_quality == "good"),
            "moderate": sum(1 for m in matches if m.match_quality == "moderate"),
            "weak": sum(1 for m in matches if m.match_quality == "weak")
        }
        
        return {
            "total": len(matches),
            "score_stats": {
                "min": min(scores),
                "max": max(scores),
                "avg": sum(scores) / len(scores)
            },
            "distance_stats": {
                "min_km": min(distances),
                "max_km": max(distances),
                "avg_km": sum(distances) / len(distances)
            },
            "quality_distribution": quality_counts,
            "feasibility_count": sum(
                1 for m in matches if m.is_economically_feasible is True
            )
        }
    
    def explain_match(self, match: MatchResult) -> str:
        """Eşleşme açıklaması"""
        quality_texts = {
            "excellent": "Mükemmel",
            "good": "İyi",
            "moderate": "Orta",
            "weak": "Zayıf"
        }
        
        explanation = f"""
Eşleşme Açıklaması
==================
Kaynak Tesis: {match.source_id}
Alıcı Tesis: {match.receiver_id}
Atık Kodu: {match.ewc_code}

Genel Skor: {match.overall_score:.2%} ({quality_texts.get(match.match_quality, 'Bilinmiyor')})

Detay Skorları:
- Teknik Uyumluluk: {match.technical_score:.2%}
- Zamansal Uyumluluk: {match.temporal_score:.2%}
- Coğrafi Uyumluluk: {match.distance_score:.2%}

Mesafe: {match.distance_km:.1f} km

"""
        
        if match.is_economically_feasible is not None:
            status = "✅ Uygulanabilir" if match.is_economically_feasible else "❌ Ekonomik Değil"
            explanation += f"Ekonomik Durum: {status}\n"
        
        return explanation
