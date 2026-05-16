"""
ATIK AI - Temporal Matcher
Zamansal ve mevsimsel uyumluluk analizi

Katman 2: Zamansal Uyumluluk
- Mevsimsel atık üretim kalıpları
- Depolama kapasitesi ve süreleri
- Üretim-tüketim senkronizasyonu
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from enum import Enum
import calendar

from ..core.exceptions import MatchingError

logger = logging.getLogger(__name__)


class Season(Enum):
    """Mevsimler"""
    WINTER = "winter"    # Aralık, Ocak, Şubat
    SPRING = "spring"    # Mart, Nisan, Mayıs
    SUMMER = "summer"    # Haziran, Temmuz, Ağustos
    AUTUMN = "autumn"    # Eylül, Ekim, Kasım


@dataclass
class SeasonalPattern:
    """Mevsimsel üretim/tüketim kalıbı"""
    entity_id: int           # Tesis veya atık tipi ID
    entity_type: str         # "facility" veya "waste_type"
    
    # Mevsimsel oranlar (toplam = 4.0 olacak şekilde normalize)
    winter: float = 1.0
    spring: float = 1.0
    summer: float = 1.0
    autumn: float = 1.0
    
    # Peak period
    peak_months: List[int] = None    # [7, 8] = Temmuz, Ağustos
    low_months: List[int] = None     # [1, 2] = Ocak, Şubat
    
    def get_season_ratio(self, season: Season) -> float:
        """Mevsim oranını al"""
        return getattr(self, season.value, 1.0)
    
    def get_monthly_ratio(self, month: int) -> float:
        """Ay bazında oran"""
        if self.peak_months and month in self.peak_months:
            return 1.5
        if self.low_months and month in self.low_months:
            return 0.5
        return 1.0


class TemporalMatcher:
    """
    Zamansal Eşleştirici
    
    Atık üretimi ve tüketiminin zamansal senkronizasyonunu analiz eder.
    """
    
    # Varsayılan endüstri mevsimsel kalıpları
    INDUSTRY_PATTERNS = {
        # Tarım (NACE A)
        "A": SeasonalPattern(
            entity_id=0, entity_type="nace",
            winter=0.3, spring=1.2, summer=1.5, autumn=1.0,
            peak_months=[6, 7, 8, 9], low_months=[12, 1, 2]
        ),
        # Gıda işleme (NACE 10-11)
        "10": SeasonalPattern(
            entity_id=0, entity_type="nace",
            winter=0.8, spring=1.1, summer=1.3, autumn=0.8,
            peak_months=[7, 8, 9], low_months=[1, 2]
        ),
        # İnşaat (NACE 41-43)
        "41": SeasonalPattern(
            entity_id=0, entity_type="nace",
            winter=0.5, spring=1.2, summer=1.3, autumn=1.0,
            peak_months=[6, 7, 8], low_months=[12, 1, 2]
        ),
        # Tekstil (NACE 13-14)
        "13": SeasonalPattern(
            entity_id=0, entity_type="nace",
            winter=1.2, spring=0.9, summer=0.8, autumn=1.1,
            peak_months=[10, 11, 12], low_months=[6, 7]
        ),
        # Turizm (NACE 55)
        "55": SeasonalPattern(
            entity_id=0, entity_type="nace",
            winter=0.4, spring=0.9, summer=1.8, autumn=0.9,
            peak_months=[6, 7, 8], low_months=[1, 2, 3]
        ),
    }
    
    # Atık tipi mevsimsel kalıpları
    WASTE_PATTERNS = {
        # Tarımsal atıklar (EWC 02)
        "02": SeasonalPattern(
            entity_id=0, entity_type="ewc",
            winter=0.3, spring=1.0, summer=1.5, autumn=1.2,
            peak_months=[8, 9, 10], low_months=[1, 2, 3]
        ),
        # Gıda atıkları (EWC 02 01-07)
        "02 01": SeasonalPattern(
            entity_id=0, entity_type="ewc",
            winter=0.5, spring=1.1, summer=1.4, autumn=1.0,
            peak_months=[7, 8, 9], low_months=[1, 2]
        ),
        # İnşaat atıkları (EWC 17)
        "17": SeasonalPattern(
            entity_id=0, entity_type="ewc",
            winter=0.6, spring=1.2, summer=1.2, autumn=1.0,
            peak_months=[5, 6, 7, 8], low_months=[12, 1, 2]
        ),
        # Belediye atıkları (EWC 20)
        "20": SeasonalPattern(
            entity_id=0, entity_type="ewc",
            winter=0.9, spring=1.0, summer=1.1, autumn=1.0,
            peak_months=[6, 7, 8], low_months=[1, 2]
        ),
    }
    
    def __init__(
        self,
        custom_patterns: Dict[str, SeasonalPattern] = None
    ):
        self.industry_patterns = {**self.INDUSTRY_PATTERNS}
        self.waste_patterns = {**self.WASTE_PATTERNS}
        
        if custom_patterns:
            for key, pattern in custom_patterns.items():
                if key.startswith("A-U") or key[0].isalpha():
                    self.industry_patterns[key] = pattern
                else:
                    self.waste_patterns[key] = pattern
    
    @staticmethod
    def get_current_season() -> Season:
        """Mevcut mevsim"""
        month = datetime.now().month
        return TemporalMatcher.month_to_season(month)
    
    @staticmethod
    def month_to_season(month: int) -> Season:
        """Ay'ı mevsime dönüştür"""
        if month in [12, 1, 2]:
            return Season.WINTER
        elif month in [3, 4, 5]:
            return Season.SPRING
        elif month in [6, 7, 8]:
            return Season.SUMMER
        else:
            return Season.AUTUMN
    
    def get_industry_pattern(self, nace: str) -> Optional[SeasonalPattern]:
        """NACE koduna göre endüstri kalıbı"""
        # Tam eşleşme
        if nace in self.industry_patterns:
            return self.industry_patterns[nace]
        
        # 2 haneli eşleşme
        if len(nace) >= 2:
            prefix = nace[:2]
            if prefix in self.industry_patterns:
                return self.industry_patterns[prefix]
        
        # Ana sektör eşleşme
        if nace and nace[0].isalpha():
            if nace[0] in self.industry_patterns:
                return self.industry_patterns[nace[0]]
        
        return None
    
    def get_waste_pattern(self, ewc: str) -> Optional[SeasonalPattern]:
        """EWC koduna göre atık kalıbı"""
        ewc_clean = ewc.replace(" ", " ").strip()
        
        # Tam eşleşme
        if ewc_clean in self.waste_patterns:
            return self.waste_patterns[ewc_clean]
        
        # Kısmi eşleşme (ilk 5 karakter: "XX XX")
        if len(ewc_clean) >= 5:
            prefix = ewc_clean[:5]
            if prefix in self.waste_patterns:
                return self.waste_patterns[prefix]
        
        # Ana kategori (ilk 2 karakter)
        if len(ewc_clean) >= 2:
            main = ewc_clean[:2]
            if main in self.waste_patterns:
                return self.waste_patterns[main]
        
        return None
    
    def calculate_temporal_score(
        self,
        source_nace: str,
        receiver_nace: str,
        ewc: str,
        target_date: date = None
    ) -> Dict:
        """
        Zamansal uyumluluk skoru
        
        Args:
            source_nace: Kaynak NACE kodu
            receiver_nace: Alıcı NACE kodu
            ewc: Atık EWC kodu
            target_date: Hedef tarih (varsayılan: bugün)
            
        Returns:
            Zamansal analiz sonucu
        """
        target_date = target_date or date.today()
        month = target_date.month
        season = self.month_to_season(month)
        
        # Kalıpları al
        source_pattern = self.get_industry_pattern(source_nace)
        receiver_pattern = self.get_industry_pattern(receiver_nace)
        waste_pattern = self.get_waste_pattern(ewc)
        
        # Kaynak üretim oranı
        source_ratio = 1.0
        if source_pattern:
            source_ratio = source_pattern.get_monthly_ratio(month)
        if waste_pattern:
            source_ratio *= waste_pattern.get_monthly_ratio(month)
        
        # Alıcı tüketim oranı
        receiver_ratio = 1.0
        if receiver_pattern:
            receiver_ratio = receiver_pattern.get_monthly_ratio(month)
        
        # Senkronizasyon skoru
        # İdeal: ikisi de yüksek veya ikisi de düşük
        if source_ratio > 1.0 and receiver_ratio > 1.0:
            sync_score = 1.0  # Her ikisi de peak dönemde
        elif source_ratio < 1.0 and receiver_ratio < 1.0:
            sync_score = 0.8  # Her ikisi de düşük dönemde
        elif source_ratio > 1.0 and receiver_ratio < 1.0:
            sync_score = 0.5  # Kaynak peak, alıcı düşük (depolama gerekli)
        else:
            sync_score = 0.7  # Kaynak düşük, alıcı yüksek
        
        # Genel zamansal skor
        temporal_score = (sync_score + (source_ratio * receiver_ratio) / 2) / 2
        temporal_score = min(1.0, temporal_score)
        
        return {
            "date": target_date.isoformat(),
            "month": month,
            "season": season.value,
            "source_ratio": round(source_ratio, 2),
            "receiver_ratio": round(receiver_ratio, 2),
            "sync_score": round(sync_score, 2),
            "temporal_score": round(temporal_score, 3),
            "recommendation": self._get_recommendation(source_ratio, receiver_ratio)
        }
    
    def _get_recommendation(
        self,
        source_ratio: float,
        receiver_ratio: float
    ) -> str:
        """Zamansal öneri"""
        if source_ratio > 1.2 and receiver_ratio > 1.2:
            return "Optimal dönem - hemen eşleştir"
        elif source_ratio > 1.2 and receiver_ratio < 0.8:
            return "Depolama gerekli - alıcı düşük kapasitede"
        elif source_ratio < 0.8 and receiver_ratio > 1.2:
            return "Miktar düşük - bekleme veya biriktirme önerilir"
        elif source_ratio < 0.8 and receiver_ratio < 0.8:
            return "Düşük aktivite dönemi - uzun vadeli planlama yap"
        else:
            return "Normal dönem - standart eşleştirme"
    
    def predict_availability(
        self,
        source_nace: str,
        ewc: str,
        start_date: date,
        months_ahead: int = 6
    ) -> List[Dict]:
        """
        Gelecek aylar için atık üretim tahmini
        
        Args:
            source_nace: Kaynak NACE kodu
            ewc: Atık EWC kodu
            start_date: Başlangıç tarihi
            months_ahead: Kaç ay ileri tahmin
            
        Returns:
            Aylık tahmin listesi
        """
        predictions = []
        
        source_pattern = self.get_industry_pattern(source_nace)
        waste_pattern = self.get_waste_pattern(ewc)
        
        current = start_date
        for _ in range(months_ahead):
            month = current.month
            
            # Üretim oranı
            ratio = 1.0
            if source_pattern:
                ratio *= source_pattern.get_monthly_ratio(month)
            if waste_pattern:
                ratio *= waste_pattern.get_monthly_ratio(month)
            
            # Peak/Low durumu
            season = self.month_to_season(month)
            is_peak = ratio > 1.2
            is_low = ratio < 0.8
            
            predictions.append({
                "date": current.isoformat(),
                "month": month,
                "month_name": calendar.month_name[month],
                "season": season.value,
                "production_ratio": round(ratio, 2),
                "is_peak": is_peak,
                "is_low": is_low
            })
            
            # Sonraki ay
            if month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=month + 1)
        
        return predictions
    
    def find_best_timing(
        self,
        source_nace: str,
        receiver_nace: str,
        ewc: str,
        start_date: date = None,
        months_ahead: int = 12
    ) -> Dict:
        """
        En iyi eşleşme zamanını bul
        
        Returns:
            En optimal aylar ve skorları
        """
        start_date = start_date or date.today()
        
        monthly_scores = []
        current = start_date
        
        for _ in range(months_ahead):
            result = self.calculate_temporal_score(
                source_nace, receiver_nace, ewc, current
            )
            monthly_scores.append({
                "date": current.isoformat(),
                "month": current.month,
                "month_name": calendar.month_name[current.month],
                "score": result["temporal_score"]
            })
            
            # Sonraki ay
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        # En iyi ayları bul
        monthly_scores.sort(key=lambda x: x["score"], reverse=True)
        
        best_months = monthly_scores[:3]
        worst_months = monthly_scores[-3:]
        
        return {
            "best_months": best_months,
            "worst_months": worst_months,
            "optimal_month": best_months[0] if best_months else None,
            "average_score": sum(m["score"] for m in monthly_scores) / len(monthly_scores)
        }
    
    def check_storage_requirement(
        self,
        source_availability: date,
        receiver_need: date,
        max_storage_days: int = 30
    ) -> Dict:
        """
        Depolama gereksinimi kontrolü
        
        Args:
            source_availability: Kaynaktan ne zaman alınabileceği
            receiver_need: Alıcının ne zaman ihtiyaç duyduğu
            max_storage_days: Maksimum depolama süresi
            
        Returns:
            Depolama analizi
        """
        delta = (receiver_need - source_availability).days
        
        if delta < 0:
            return {
                "storage_required": False,
                "days_early": abs(delta),
                "status": "receiver_early",
                "message": f"Alıcı {abs(delta)} gün önce hazır"
            }
        elif delta == 0:
            return {
                "storage_required": False,
                "days": 0,
                "status": "synchronized",
                "message": "Mükemmel zamanlama"
            }
        elif delta <= max_storage_days:
            return {
                "storage_required": True,
                "days": delta,
                "status": "feasible",
                "message": f"{delta} gün depolama gerekli"
            }
        else:
            return {
                "storage_required": True,
                "days": delta,
                "status": "too_long",
                "message": f"{delta} gün çok uzun (max: {max_storage_days})",
                "exceeded_by": delta - max_storage_days
            }
