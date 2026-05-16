"""
ATIK AI - Technical Matcher
NACE-EWC tabanlı teknik eşleşme

Katman 1: Teknik Uyumluluk
- EWC kodu uyumu
- NACE sektör uyumu
- Üretilen-İhtiyaç atık tipi eşleşmesi
"""
import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
import re

from ..core.exceptions import MatchingError
from ..config import config

logger = logging.getLogger(__name__)


@dataclass
class TechnicalRule:
    """Teknik eşleşme kuralı"""
    source_ewc: str          # Kaynak EWC kodu (regex pattern)
    receiver_nace: str       # Alıcı NACE kodu (regex pattern)
    waste_category: str      # Atık kategorisi
    compatibility: float     # Uyumluluk skoru [0-1]
    process_type: str        # İşlem tipi (R: Recovery, D: Disposal)
    constraints: Dict = None # Ek kısıtlar
    
    def to_dict(self) -> dict:
        return {
            "source_ewc": self.source_ewc,
            "receiver_nace": self.receiver_nace,
            "waste_category": self.waste_category,
            "compatibility": self.compatibility,
            "process_type": self.process_type,
            "constraints": self.constraints
        }


class TechnicalMatcher:
    """
    Teknik Eşleştirici
    
    NACE-EWC kuralları ile atık-tesis uyumluluğunu değerlendirir.
    
    EWC Kodu Yapısı:
    - XX: Ana kategori (01-20)
    - XX XX: Alt kategori
    - XX XX XX: Spesifik atık
    
    NACE Kodu Yapısı:
    - A-U: Ana sektör
    - XX: Alt sektör
    - XX.X: Grup
    - XX.XX: Sınıf
    """
    
    # Varsayılan NACE-EWC eşleşme kuralları
    DEFAULT_RULES = [
        # Tarımsal atıklar
        TechnicalRule("02.*", r"A\d{2}", "agricultural", 0.9, "R"),
        TechnicalRule("02 01.*", r"10\.\d{2}", "food_processing", 0.85, "R"),
        
        # Gıda atıkları
        TechnicalRule("02 02.*", r"10\.\d{2}", "food_waste", 0.9, "R"),
        TechnicalRule("02 03.*", r"10\.\d{2}", "food_waste", 0.9, "R"),
        
        # Kağıt/karton
        TechnicalRule("15 01 01", r"17\.\d{2}", "paper", 0.95, "R"),
        TechnicalRule("19 12 01", r"17\.\d{2}", "paper", 0.95, "R"),
        
        # Plastik
        TechnicalRule("15 01 02", r"22\.\d{2}", "plastic", 0.9, "R"),
        TechnicalRule("17 02 03", r"22\.\d{2}", "plastic", 0.85, "R"),
        
        # Metal
        TechnicalRule("15 01 04", r"24\.\d{2}|25\.\d{2}", "metal", 0.95, "R"),
        TechnicalRule("17 04.*", r"24\.\d{2}|25\.\d{2}", "metal", 0.9, "R"),
        TechnicalRule("19 12 02", r"24\.\d{2}|25\.\d{2}", "metal", 0.95, "R"),
        
        # Cam
        TechnicalRule("15 01 07", r"23\.1\d", "glass", 0.9, "R"),
        TechnicalRule("17 02 02", r"23\.1\d", "glass", 0.85, "R"),
        
        # Tekstil
        TechnicalRule("04 02.*", r"13\.\d{2}|14\.\d{2}", "textile", 0.8, "R"),
        TechnicalRule("15 01 09", r"13\.\d{2}|14\.\d{2}", "textile", 0.75, "R"),
        
        # Ahşap
        TechnicalRule("03 01.*", r"16\.\d{2}|31\.\d{2}", "wood", 0.85, "R"),
        TechnicalRule("15 01 03", r"16\.\d{2}|31\.\d{2}", "wood", 0.9, "R"),
        TechnicalRule("17 02 01", r"16\.\d{2}|31\.\d{2}", "wood", 0.8, "R"),
        
        # İnşaat/yıkım
        TechnicalRule("17 01.*", r"23\.\d{2}", "construction", 0.7, "R"),
        TechnicalRule("17 05 04", r"42\.\d{2}", "soil", 0.6, "R"),
        
        # Kimyasal
        TechnicalRule("07 0[1-7].*", r"20\.\d{2}|21\.\d{2}", "chemical", 0.5, "R"),
        
        # Elektronik
        TechnicalRule("16 02.*", r"26\.\d{2}|27\.\d{2}", "electronic", 0.8, "R"),
        
        # Organik / Kompost
        TechnicalRule("20 01 08", r"01\.\d{2}", "organic_compost", 0.85, "R"),
        TechnicalRule("20 02 01", r"01\.\d{2}", "organic_compost", 0.9, "R"),
        
        # Enerji üretimi
        TechnicalRule("19 12 10", r"35\.1\d", "energy", 0.7, "R"),
    ]
    
    def __init__(self, rules: List[TechnicalRule] = None):
        self.rules = rules or self.DEFAULT_RULES
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Regex pattern'leri önceden derle"""
        self._compiled_rules = []
        
        for rule in self.rules:
            try:
                ewc_pattern = re.compile(rule.source_ewc.replace(" ", r"\s*"), re.IGNORECASE)
                nace_pattern = re.compile(rule.receiver_nace, re.IGNORECASE)
                
                self._compiled_rules.append({
                    "rule": rule,
                    "ewc_pattern": ewc_pattern,
                    "nace_pattern": nace_pattern
                })
            except re.error as e:
                logger.warning(f"Invalid pattern in rule: {rule.source_ewc} -> {rule.receiver_nace}: {e}")
    
    def find_matching_rules(
        self,
        source_ewc: str,
        receiver_nace: str
    ) -> List[TechnicalRule]:
        """
        EWC-NACE çifti için eşleşen kuralları bul
        
        Args:
            source_ewc: Kaynak EWC kodu
            receiver_nace: Alıcı NACE kodu
            
        Returns:
            Eşleşen kurallar listesi
        """
        matching = []
        
        for compiled in self._compiled_rules:
            if (compiled["ewc_pattern"].match(source_ewc) and 
                compiled["nace_pattern"].match(receiver_nace)):
                matching.append(compiled["rule"])
        
        # Uyumluluk skoruna göre sırala
        matching.sort(key=lambda r: r.compatibility, reverse=True)
        
        return matching
    
    def check_compatibility(
        self,
        source_ewc: str,
        receiver_nace: str
    ) -> Tuple[bool, float, Optional[TechnicalRule]]:
        """
        Teknik uyumluluk kontrolü
        
        Args:
            source_ewc: Kaynak EWC kodu
            receiver_nace: Alıcı NACE kodu
            
        Returns:
            (is_compatible, compatibility_score, matching_rule)
        """
        rules = self.find_matching_rules(source_ewc, receiver_nace)
        
        if rules:
            best_rule = rules[0]
            return True, best_rule.compatibility, best_rule
        
        # EWC ana kategori kontrolü (genel eşleşme)
        ewc_main = source_ewc[:2] if source_ewc else ""
        general_score = self._check_general_compatibility(ewc_main, receiver_nace)
        
        if general_score > 0:
            return True, general_score, None
        
        return False, 0.0, None
    
    def _check_general_compatibility(self, ewc_main: str, nace: str) -> float:
        """Genel uyumluluk kontrolü (kural yoksa)"""
        # Geri dönüşüm tesisleri (38.xx) çoğu atığı kabul edebilir
        if nace.startswith("38"):
            return 0.5
        
        # Enerji üretimi (35.xx) yanabilir atıkları kabul edebilir
        if nace.startswith("35") and ewc_main in ["03", "15", "17", "19", "20"]:
            return 0.4
        
        return 0.0
    
    def evaluate_waste_profile_match(
        self,
        source_produces: List[str],   # Kaynağın ürettiği EWC kodları
        receiver_needs: List[str],     # Alıcının ihtiyaç duyduğu EWC kodları
        receiver_nace: str
    ) -> Dict:
        """
        Atık profili eşleşmesi
        
        Args:
            source_produces: Kaynağın ürettiği atıklar
            receiver_needs: Alıcının kabul ettiği atıklar
            receiver_nace: Alıcının NACE kodu
            
        Returns:
            Eşleşme raporu
        """
        matches = []
        total_score = 0
        
        for ewc in source_produces:
            # Direkt eşleşme
            if ewc in receiver_needs:
                matches.append({
                    "ewc": ewc,
                    "match_type": "direct",
                    "score": 1.0
                })
                total_score += 1.0
                continue
            
            # Kural tabanlı eşleşme
            is_compat, score, rule = self.check_compatibility(ewc, receiver_nace)
            if is_compat:
                matches.append({
                    "ewc": ewc,
                    "match_type": "rule_based",
                    "score": score,
                    "rule_category": rule.waste_category if rule else "general"
                })
                total_score += score
        
        avg_score = total_score / len(source_produces) if source_produces else 0
        
        return {
            "matches": matches,
            "match_count": len(matches),
            "total_ewc_count": len(source_produces),
            "average_score": round(avg_score, 3),
            "is_compatible": avg_score > 0.3
        }
    
    def get_potential_receivers(
        self,
        source_ewc: str,
        available_nace_codes: List[str]
    ) -> List[Dict]:
        """
        Bir EWC kodu için potansiyel alıcı NACE kodlarını bul
        
        Args:
            source_ewc: Kaynak EWC kodu
            available_nace_codes: Mevcut alıcı NACE kodları
            
        Returns:
            Potansiyel alıcılar listesi
        """
        potentials = []
        
        for nace in available_nace_codes:
            is_compat, score, rule = self.check_compatibility(source_ewc, nace)
            if is_compat:
                potentials.append({
                    "nace": nace,
                    "compatibility_score": score,
                    "process_type": rule.process_type if rule else "R",
                    "category": rule.waste_category if rule else "general"
                })
        
        # Skora göre sırala
        potentials.sort(key=lambda x: x["compatibility_score"], reverse=True)
        
        return potentials
    
    def add_rule(self, rule: TechnicalRule):
        """Yeni kural ekle"""
        self.rules.append(rule)
        self._compile_patterns()
    
    def get_rules_by_category(self, category: str) -> List[TechnicalRule]:
        """Kategoriye göre kuralları getir"""
        return [r for r in self.rules if r.waste_category == category]
    
    def validate_ewc_code(self, ewc: str) -> bool:
        """EWC kodu format kontrolü"""
        # XX XX XX formatı
        pattern = r"^\d{2}(\s\d{2}){0,2}(\s?\*)?$"
        return bool(re.match(pattern, ewc.strip()))
    
    def validate_nace_code(self, nace: str) -> bool:
        """NACE kodu format kontrolü"""
        # XX.XX veya A-U formatı
        pattern = r"^([A-U]|\d{2})(\.\d{1,2})?$"
        return bool(re.match(pattern, nace.strip(), re.IGNORECASE))
    
    def get_ewc_categories(self) -> Dict[str, str]:
        """EWC ana kategorileri"""
        return {
            "01": "Maden ve taş ocakları atıkları",
            "02": "Tarım, bahçecilik, avcılık, balıkçılık ve su ürünleri atıkları",
            "03": "Ağaç, kağıt, karton işleme atıkları",
            "04": "Deri, kürk ve tekstil endüstrisi atıkları",
            "05": "Petrol rafinasyonu ve doğalgaz arıtma atıkları",
            "06": "İnorganik kimyasal işlem atıkları",
            "07": "Organik kimyasal işlem atıkları",
            "08": "Kaplama, boya, vernik atıkları",
            "09": "Fotoğrafçılık endüstrisi atıkları",
            "10": "Termal işlem atıkları",
            "11": "Metal yüzey işleme atıkları",
            "12": "Metal ve plastik şekillendirme atıkları",
            "13": "Yağ atıkları",
            "14": "Çözücü atıkları",
            "15": "Ambalaj atıkları",
            "16": "Diğer atıklar",
            "17": "İnşaat ve yıkım atıkları",
            "18": "Sağlık ve veterinerlik atıkları",
            "19": "Atık yönetim tesisi atıkları",
            "20": "Belediye atıkları"
        }
