"""
ATIK AI - Hybrid Pricing Engine
================================
LLM-free, deterministic + uncertainty-aware fiyatlandırma motoru.

Mimari:
  EWC kodu → feature mapping (rule-based)
           → heuristic formül (deterministic)
           → range + confidence score
           → PriceEstimate (value, low, high, confidence, source)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import math


# =============================================================================
# SYSTEM CONSTANTS
# =============================================================================

TRUCK_CAPACITY_TON          = 20
FUEL_CONSUMPTION_L_PER_100KM = 32.5
FUEL_PRICE_TRY_PER_L        = 44.0
DRIVER_COST_TRY_PER_KM      = 3.5
MAINTENANCE_TRY_PER_KM      = 2.0
LOADING_UNLOADING_FIXED_TRY = 2500

# Depolama maliyeti sabitleri
DEFAULT_FACILITY_STORAGE_COST = 150.0   # Varsayılan tesis depolama maliyeti (₺/ton/gün)

# Ticari fiyat hesaplama katsayıları
COMMERCIAL_BASE_PRICE       = 2_000     # Baz ticari fiyat (₺/ton)
COMMERCIAL_RECYCLABILITY    = 8_000     # Geri dönüşüm çarpanı
COMMERCIAL_DEMAND           = 5_000     # Talep çarpanı
COMMERCIAL_PURITY           = 3_000     # Saflık bonusu


# =============================================================================
# PRICE ESTIMATE — tek çıktı tipi
# =============================================================================

@dataclass
class PriceEstimate:
    """
    Tüm fiyat hesaplamalarının standart çıktısı.

    value      : Merkezi tahmin (₺/ton)
    low / high : %80 güven aralığı
    confidence : 0.0–1.0  (1.0 = gerçek piyasa verisi, 0.0 = saf tahmin)
    source     : "market_data" | "heuristic_model" | "default_fallback"
    """
    value:      float
    low:        float
    high:       float
    confidence: float
    source:     str

    def __str__(self) -> str:
        stars = round(self.confidence * 5)
        bar   = "★" * stars + "☆" * (5 - stars)
        return (
            f"{self.value:>8.0f} ₺/ton  "
            f"[{self.low:.0f} – {self.high:.0f}]  "
            f"güven: {bar} ({self.confidence:.0%})  "
            f"kaynak: {self.source}"
        )


# =============================================================================
# FEATURE MAPPING  (EWC → fiziksel/ekonomik özellikler)
# =============================================================================
# Tüm değerler 0.0–1.0 aralığında normalize edilmiştir.
#
# hazard       : 0 = tehlikesiz, 1 = çok tehlikeli
# recyclability: 0 = geri dönüştürülemez, 1 = kolay geri dönüşüm
# market_demand: 0 = pazar yok, 1 = yüksek talep
# purity       : 0 = kirli/karışık, 1 = saf/temiz
# volume_index : 0 = nadir, 1 = yüksek hacimli (lojistik verimliliği)
#
# confidence   : Bu eşlemenin güvenilirliği (kaynak kalitesi)
# =============================================================================

EWC_FEATURES: Dict[str, Dict] = {
    # ── Plastik / Organik ───────────────────────────────────────────────────
    "70213":  {"hazard": 0.0, "recyclability": 0.95, "market_demand": 0.90, "purity": 0.85, "volume_index": 0.7, "confidence": 0.80},
    "200139": {"hazard": 0.0, "recyclability": 0.80, "market_demand": 0.80, "purity": 0.55, "volume_index": 0.9, "confidence": 0.75},
    "30105":  {"hazard": 0.0, "recyclability": 0.90, "market_demand": 0.85, "purity": 0.80, "volume_index": 0.6, "confidence": 0.78},
    "200111": {"hazard": 0.0, "recyclability": 0.75, "market_demand": 0.70, "purity": 0.60, "volume_index": 0.5, "confidence": 0.70},

    # ── Tekstil / Organik ───────────────────────────────────────────────────
    "191212": {"hazard": 0.1, "recyclability": 0.55, "market_demand": 0.50, "purity": 0.50, "volume_index": 0.5, "confidence": 0.60},
    "150106": {"hazard": 0.1, "recyclability": 0.50, "market_demand": 0.45, "purity": 0.45, "volume_index": 0.6, "confidence": 0.60},

    # ── Endüstriyel / Metalürji cürufu ──────────────────────────────────────
    "100903": {"hazard": 0.1, "recyclability": 0.45, "market_demand": 0.40, "purity": 0.40, "volume_index": 0.7, "confidence": 0.65},
    "100809": {"hazard": 0.1, "recyclability": 0.40, "market_demand": 0.35, "purity": 0.35, "volume_index": 0.6, "confidence": 0.65},
    "100910": {"hazard": 0.1, "recyclability": 0.40, "market_demand": 0.30, "purity": 0.40, "volume_index": 0.5, "confidence": 0.60},
    "100201": {"hazard": 0.1, "recyclability": 0.35, "market_demand": 0.30, "purity": 0.35, "volume_index": 0.6, "confidence": 0.60},
    "100101": {"hazard": 0.1, "recyclability": 0.25, "market_demand": 0.25, "purity": 0.30, "volume_index": 0.7, "confidence": 0.60},

    # ── Belediye atığı ──────────────────────────────────────────────────────
    "190805": {"hazard": 0.2, "recyclability": 0.40, "market_demand": 0.35, "purity": 0.30, "volume_index": 0.8, "confidence": 0.65},
    "190802": {"hazard": 0.1, "recyclability": 0.30, "market_demand": 0.25, "purity": 0.30, "volume_index": 0.6, "confidence": 0.55},
    "190801": {"hazard": 0.1, "recyclability": 0.15, "market_demand": 0.15, "purity": 0.20, "volume_index": 0.7, "confidence": 0.55},
    "200301": {"hazard": 0.2, "recyclability": 0.20, "market_demand": 0.15, "purity": 0.15, "volume_index": 0.9, "confidence": 0.70},

    # ── Tehlikeli / Kimyasal ─────────────────────────────────────────────────
    "80111":  {"hazard": 0.95, "recyclability": 0.05, "market_demand": 0.05, "purity": 0.20, "volume_index": 0.3, "confidence": 0.80},
    "80113":  {"hazard": 0.85, "recyclability": 0.08, "market_demand": 0.05, "purity": 0.20, "volume_index": 0.3, "confidence": 0.78},
    "80117":  {"hazard": 0.88, "recyclability": 0.05, "market_demand": 0.05, "purity": 0.15, "volume_index": 0.3, "confidence": 0.75},
    "80409":  {"hazard": 0.80, "recyclability": 0.08, "market_demand": 0.08, "purity": 0.20, "volume_index": 0.3, "confidence": 0.72},
    "170603": {"hazard": 1.00, "recyclability": 0.00, "market_demand": 0.00, "purity": 0.10, "volume_index": 0.2, "confidence": 0.90},
    "110111": {"hazard": 0.90, "recyclability": 0.05, "market_demand": 0.05, "purity": 0.10, "volume_index": 0.4, "confidence": 0.78},
    "190205": {"hazard": 0.85, "recyclability": 0.08, "market_demand": 0.08, "purity": 0.15, "volume_index": 0.5, "confidence": 0.72},
    "150202": {"hazard": 0.85, "recyclability": 0.05, "market_demand": 0.05, "purity": 0.15, "volume_index": 0.3, "confidence": 0.75},
    "150110": {"hazard": 0.80, "recyclability": 0.08, "market_demand": 0.08, "purity": 0.15, "volume_index": 0.3, "confidence": 0.72},
    "120109": {"hazard": 0.80, "recyclability": 0.08, "market_demand": 0.08, "purity": 0.20, "volume_index": 0.4, "confidence": 0.70},
    "120116": {"hazard": 0.82, "recyclability": 0.05, "market_demand": 0.05, "purity": 0.15, "volume_index": 0.3, "confidence": 0.72},
    "160305": {"hazard": 0.88, "recyclability": 0.05, "market_demand": 0.05, "purity": 0.10, "volume_index": 0.3, "confidence": 0.75},
    "160107": {"hazard": 0.80, "recyclability": 0.10, "market_demand": 0.10, "purity": 0.20, "volume_index": 0.3, "confidence": 0.70},

    # ── Piller / Elektronik ─────────────────────────────────────────────────
    "160602": {"hazard": 0.75, "recyclability": 0.30, "market_demand": 0.25, "purity": 0.40, "volume_index": 0.3, "confidence": 0.68},
    "200133": {"hazard": 0.65, "recyclability": 0.30, "market_demand": 0.25, "purity": 0.35, "volume_index": 0.4, "confidence": 0.65},
    "200134": {"hazard": 0.30, "recyclability": 0.45, "market_demand": 0.35, "purity": 0.40, "volume_index": 0.4, "confidence": 0.65},
    "160604": {"hazard": 0.35, "recyclability": 0.40, "market_demand": 0.30, "purity": 0.40, "volume_index": 0.4, "confidence": 0.60},

    # ── Tehlikeli Metalürji ─────────────────────────────────────────────────
    "100308": {"hazard": 0.75, "recyclability": 0.15, "market_demand": 0.15, "purity": 0.20, "volume_index": 0.4, "confidence": 0.68},
    "100309": {"hazard": 0.80, "recyclability": 0.10, "market_demand": 0.10, "purity": 0.15, "volume_index": 0.4, "confidence": 0.68},
    "100321": {"hazard": 0.80, "recyclability": 0.15, "market_demand": 0.15, "purity": 0.20, "volume_index": 0.4, "confidence": 0.68},
    "100401": {"hazard": 0.85, "recyclability": 0.10, "market_demand": 0.10, "purity": 0.15, "volume_index": 0.4, "confidence": 0.70},
    "100908": {"hazard": 0.75, "recyclability": 0.15, "market_demand": 0.15, "purity": 0.20, "volume_index": 0.4, "confidence": 0.65},
    "100319": {"hazard": 0.80, "recyclability": 0.10, "market_demand": 0.10, "purity": 0.15, "volume_index": 0.4, "confidence": 0.68},
    "100915": {"hazard": 0.78, "recyclability": 0.10, "market_demand": 0.10, "purity": 0.15, "volume_index": 0.4, "confidence": 0.65},
    "101006": {"hazard": 0.72, "recyclability": 0.15, "market_demand": 0.15, "purity": 0.20, "volume_index": 0.4, "confidence": 0.62},

    # ── Diğer ──────────────────────────────────────────────────────────────
    "30104":  {"hazard": 0.70, "recyclability": 0.15, "market_demand": 0.15, "purity": 0.25, "volume_index": 0.4, "confidence": 0.65},
    "70215":  {"hazard": 0.78, "recyclability": 0.10, "market_demand": 0.10, "purity": 0.20, "volume_index": 0.3, "confidence": 0.65},
    "110108": {"hazard": 0.30, "recyclability": 0.30, "market_demand": 0.25, "purity": 0.30, "volume_index": 0.4, "confidence": 0.60},
    "110109": {"hazard": 0.80, "recyclability": 0.08, "market_demand": 0.08, "purity": 0.15, "volume_index": 0.3, "confidence": 0.70},
    "120112": {"hazard": 0.35, "recyclability": 0.40, "market_demand": 0.35, "purity": 0.40, "volume_index": 0.4, "confidence": 0.62},
    "170604": {"hazard": 0.15, "recyclability": 0.50, "market_demand": 0.40, "purity": 0.50, "volume_index": 0.5, "confidence": 0.65},
}


# =============================================================================
# HEURISTIC PRICING MODEL
# =============================================================================
# Formül mantığı:
#   cmm_w = recyclability × RECYCLE_COEF
#         + market_demand  × DEMAND_COEF
#         - hazard         × HAZARD_PENALTY
#         + purity         × PURITY_BONUS
#         + volume_index   × VOLUME_BONUS
#
# Katsayılar piyasa gözlemine dayalı (Türkiye 2024-2025 atık sektörü).
# =============================================================================

RECYCLE_COEF   =  8_000   # Geri dönüşüm katsayısı (₺/ton)
DEMAND_COEF    =  5_000   # Pazar talebi katsayısı
HAZARD_PENALTY = 10_000   # Tehlikelilik cezası
PURITY_BONUS   =  2_000   # Saflık bonusu
VOLUME_BONUS   =  1_500   # Yüksek hacim / lojistik verimlilik bonusu

# Belirsizlik bantları: feature confidence'a göre aralık genişliği
UNCERTAINTY_BASE      = 0.25   # Düşük güvende ±%25
UNCERTAINTY_MIN       = 0.10   # Yüksek güvende minimum ±%10


def _uncertainty_spread(confidence: float) -> float:
    """Confidence 1.0 → %10 spread, confidence 0.0 → %35 spread."""
    return UNCERTAINTY_MIN + (UNCERTAINTY_BASE - UNCERTAINTY_MIN) * (1.0 - confidence)


def estimate_cmm_w(
    hazard:       float,
    recyclability: float,
    market_demand: float,
    purity:        float,
    volume_index:  float,
    confidence:    float,
) -> PriceEstimate:
    """
    Ham özelliklerden CMM_W (bertaraf tasarrufu, ₺/ton) tahmin eder.
    Negatif değer = bertaraf maliyeti (üretici öder).
    """
    value = (
        recyclability * RECYCLE_COEF
        + market_demand * DEMAND_COEF
        - hazard        * HAZARD_PENALTY
        + purity        * PURITY_BONUS
        + volume_index  * VOLUME_BONUS
    )

    spread = _uncertainty_spread(confidence)
    low    = value * (1 - spread)
    high   = value * (1 + spread)

    # Eğer değer negatifse low/high yer değiştirir
    if low > high:
        low, high = high, low

    return PriceEstimate(
        value=round(value, 0),
        low=round(low, 0),
        high=round(high, 0),
        confidence=round(confidence, 2),
        source="heuristic_model",
    )


# =============================================================================
# PUBLIC API
# =============================================================================

_DEFAULT_FEATURES = {
    "hazard": 0.3, "recyclability": 0.3, "market_demand": 0.3,
    "purity": 0.3, "volume_index": 0.5, "confidence": 0.30,
}


def get_cmm_w(ewc_code: str) -> PriceEstimate:
    """
    EWC kodundan CMM_W tahmini döndürür.
    Tanımsız kodlar için düşük güvenli default tahmin kullanılır.
    """
    features = EWC_FEATURES.get(ewc_code, _DEFAULT_FEATURES)
    estimate = estimate_cmm_w(**features)

    if ewc_code not in EWC_FEATURES:
        estimate.source     = "default_fallback"
        estimate.confidence = _DEFAULT_FEATURES["confidence"]

    return estimate


def get_disposal_savings(ewc_code: str) -> float:
    """
    EWC kodundan bertaraf tasarrufu (CMM_W) değerini döndürür (₺/ton).
    
    Feasibility modülü ile uyumlu: basit float döndürür.
    """
    estimate = get_cmm_w(ewc_code)
    return estimate.value


def get_commercial_price(ewc_code: str) -> float:
    """
    EWC kodundan ticari fiyat tahminini döndürür (₺/ton).
    
    Ticari fiyat = geri dönüştürülmüş/işlenmiş malzemenin piyasa değeri.
    Hesaplama: recyclability × talep × saflık faktörlerine dayalı.
    """
    features = EWC_FEATURES.get(ewc_code, _DEFAULT_FEATURES)
    
    # Tehlikeli atıklar düşük/negatif ticari değere sahip
    hazard_penalty = features["hazard"] * 6_000
    
    price = (
        COMMERCIAL_BASE_PRICE
        + features["recyclability"] * COMMERCIAL_RECYCLABILITY
        + features["market_demand"] * COMMERCIAL_DEMAND
        + features["purity"] * COMMERCIAL_PURITY
        - hazard_penalty
    )
    
    # Negatif fiyatlara izin verme (minimum 0)
    return max(0, round(price, 0))


def get_storage_cost_multiplier(ewc_code: str) -> float:
    """
    EWC kodundan depolama maliyet çarpanını döndürür.
    
    Tehlikeli atıklar için daha yüksek depolama maliyeti:
    - hazard 0.0 → çarpan 1.0
    - hazard 1.0 → çarpan 3.0 (3x daha pahalı)
    """
    features = EWC_FEATURES.get(ewc_code, _DEFAULT_FEATURES)
    
    # Tehlikelilik oranına göre 1.0 - 3.0 arasında çarpan
    multiplier = 1.0 + (features["hazard"] * 2.0)
    
    return round(multiplier, 2)


def calculate_transport_cost(
    waste_quantity_ton: float,
    distance_km: float,
    include_driver_wage: bool = True,
    include_maintenance: bool = True,
) -> Dict[str, float]:
    """
    Taşıma maliyetini hesaplar.

    Returns:
        fuel_cost, driver_wage, maintenance, loading_unloading,
        num_trucks, total, total_per_ton  (hepsi ₺)
    """
    if waste_quantity_ton <= 0:
        raise ValueError("waste_quantity_ton > 0 olmalı.")
    if distance_km < 0:
        raise ValueError("distance_km negatif olamaz.")

    num_trucks = math.ceil(waste_quantity_ton / TRUCK_CAPACITY_TON)

    fuel_cost         = (distance_km / 100) * FUEL_CONSUMPTION_L_PER_100KM * FUEL_PRICE_TRY_PER_L * num_trucks
    driver_wage       = DRIVER_COST_TRY_PER_KM * distance_km * num_trucks if include_driver_wage else 0.0
    maintenance       = MAINTENANCE_TRY_PER_KM  * distance_km * num_trucks if include_maintenance else 0.0
    loading_unloading = LOADING_UNLOADING_FIXED_TRY * num_trucks

    total         = fuel_cost + driver_wage + maintenance + loading_unloading
    total_per_ton = total / waste_quantity_ton

    return {
        "fuel_cost":         round(fuel_cost, 2),
        "driver_wage":       round(driver_wage, 2),
        "maintenance":       round(maintenance, 2),
        "loading_unloading": round(loading_unloading, 2),
        "num_trucks":        num_trucks,
        "total":             round(total, 2),
        "total_per_ton":     round(total_per_ton, 2),
    }


def get_price_summary() -> Dict:
    """Tüm EWC kodları için özet istatistikler."""
    estimates = {code: get_cmm_w(code) for code in EWC_FEATURES}
    values    = [e.value for e in estimates.values()]

    return {
        "system_constants": {
            "truck_capacity_ton":           TRUCK_CAPACITY_TON,
            "fuel_consumption_l_per_100km": FUEL_CONSUMPTION_L_PER_100KM,
            "fuel_price_try_per_l":         FUEL_PRICE_TRY_PER_L,
            "driver_cost_try_per_km":       DRIVER_COST_TRY_PER_KM,
            "maintenance_try_per_km":       MAINTENANCE_TRY_PER_KM,
            "loading_unloading_fixed_try":  LOADING_UNLOADING_FIXED_TRY,
        },
        "model_coefficients": {
            "recycle_coef":   RECYCLE_COEF,
            "demand_coef":    DEMAND_COEF,
            "hazard_penalty": HAZARD_PENALTY,
            "purity_bonus":   PURITY_BONUS,
            "volume_bonus":   VOLUME_BONUS,
        },
        "ewc_codes_covered": len(EWC_FEATURES),
        "avg_cmm_w":         round(sum(values) / len(values), 0),
        "cmm_w_range":       (round(min(values), 0), round(max(values), 0)),
        "avg_confidence":    round(sum(e.confidence for e in estimates.values()) / len(estimates), 2),
    }


# =============================================================================
# QUICK TEST
# =============================================================================

if __name__ == "__main__":
    test_codes = ["70213", "200139", "170603", "80111", "200301", "UNKNOWN"]

    print("=" * 72)
    print(f"{'EWC':<10}  {'Tahmin (₺/ton)'}")
    print("=" * 72)
    for code in test_codes:
        print(f"{code:<10}  {get_cmm_w(code)}")

    print()
    transport = calculate_transport_cost(45, 120)
    print("Taşıma (45 ton, 120 km):")
    for k, v in transport.items():
        print(f"  {k:<20}: {v}")