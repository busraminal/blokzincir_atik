"""
ATIK AI - SWAN Ekonomik Fizibilite Modeli
Deterministic ekonomik analiz ve karar sistemi

SWAN Formülleri:
1. S_profit = W×P_W + W×CMM_W - (W/C)×FC_T×P_F×D  (Kaynak kârı)
2. R_profit = W×P_COM - W×P_W - W×ST_W  (Alıcı kârı)
3. P_WBES = CMM_W - (1/C)×FC_T×P_F×D  (Min fiyat)
4. P_WBER = P_COM - ST_W  (Max fiyat)
5. Karar: P_WBES < P_WBER → Onay ✓
"""
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .pricing_table import (
    get_disposal_savings,
    get_commercial_price,
    get_storage_cost_multiplier,
    calculate_transport_cost,
    DEFAULT_FACILITY_STORAGE_COST,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TransportCostDetails:
    """Taşıma maliyeti detayları"""
    fuel_cost: float
    driver_wage: float
    maintenance: float
    loading_unloading: float
    num_trucks: int
    total_per_ton: float
    total: float


@dataclass
class SourceProfit:
    """Kaynak tesis kârı detayları (S_profit)"""
    waste_quantity_ton: float
    sale_price_per_ton: float
    quantity_revenue: float
    disposal_savings: float
    transport_cost: float
    total_profit: float
    profit_per_ton: float
    
    def to_dict(self):
        return {
            "waste_quantity_ton": self.waste_quantity_ton,
            "sale_price_per_ton": round(self.sale_price_per_ton, 2),
            "quantity_revenue": round(self.quantity_revenue, 2),
            "disposal_savings": round(self.disposal_savings, 2),
            "transport_cost": round(self.transport_cost, 2),
            "total_profit": round(self.total_profit, 2),
            "profit_per_ton": round(self.profit_per_ton, 2)
        }


@dataclass
class ReceiverProfit:
    """Alıcı tesis kârı detayları (R_profit)"""
    waste_quantity_ton: float
    commercial_price_per_ton: float
    purchase_price_per_ton: float
    revenue: float
    purchase_cost: float
    storage_cost: float
    total_profit: float
    profit_per_ton: float
    
    def to_dict(self):
        return {
            "waste_quantity_ton": self.waste_quantity_ton,
            "commercial_price_per_ton": round(self.commercial_price_per_ton, 2),
            "purchase_price_per_ton": round(self.purchase_price_per_ton, 2),
            "revenue": round(self.revenue, 2),
            "purchase_cost": round(self.purchase_cost, 2),
            "storage_cost": round(self.storage_cost, 2),
            "total_profit": round(self.total_profit, 2),
            "profit_per_ton": round(self.profit_per_ton, 2)
        }


@dataclass
class BreakEvenAnalysis:
    """Break-even analizi"""
    source_break_even_min: float
    receiver_break_even_max: float
    suggested_price: float
    negotiation_margin: float
    is_feasible: bool
    reason: str
    
    def to_dict(self):
        return {
            "source_break_even_min": round(self.source_break_even_min, 2),
            "receiver_break_even_max": round(self.receiver_break_even_max, 2),
            "suggested_price": round(self.suggested_price, 2),
            "negotiation_margin": round(self.negotiation_margin, 2),
            "is_feasible": self.is_feasible,
            "reason": self.reason
        }


@dataclass
class FeasibilityResult:
    """Fizibilite analiz sonucu (SWAN Model)"""
    source_facility_id: int
    receiver_facility_id: int
    waste_type_id: int
    ewc_code: str
    waste_quantity_ton: float
    distance_km: float
    
    # Detaylı hesaplamalar
    transport_cost_details: TransportCostDetails
    source_profit: SourceProfit
    receiver_profit: ReceiverProfit
    break_even: BreakEvenAnalysis
    
    # Karar
    is_feasible: bool
    decision_reason: str
    confidence_score: float
    
    # Metadata
    analysis_date: datetime
    model_version: str = "SWAN_v1"
    
    def to_dict(self):
        return {
            "source_facility_id": self.source_facility_id,
            "receiver_facility_id": self.receiver_facility_id,
            "waste_type_id": self.waste_type_id,
            "ewc_code": self.ewc_code,
            "waste_quantity_ton": self.waste_quantity_ton,
            "distance_km": self.distance_km,
            "transport_cost": self.transport_cost_details.__dict__,
            "source_profit": self.source_profit.to_dict(),
            "receiver_profit": self.receiver_profit.to_dict(),
            "break_even": self.break_even.to_dict(),
            "is_feasible": self.is_feasible,
            "decision_reason": self.decision_reason,
            "confidence_score": round(self.confidence_score, 2),
            "analysis_date": self.analysis_date.isoformat(),
            "model_version": self.model_version
        }


# =============================================================================
# OLD DATA CLASSES (Backward compatibility)
# ============================================================================= 

@dataclass
class FeasibilityResult_OLD:
    """Eski fizibilite sonucu (backward compat)"""
    source_facility_id: int
    receiver_facility_id: int
    waste_type_id: int
    waste_quantity_ton: float
    is_feasible: bool
    decision_reason: str
    confidence_score: float = 1.0


@dataclass
class MatchInput:
    """Fizibilite analizi girdi verisi (backward compat)"""
    source_facility_id: int
    receiver_facility_id: int
    waste_type_id: int
    waste_quantity_ton: float
    source_coords: Tuple[float, float]
    receiver_coords: Tuple[float, float]
    disposal_savings: float = 0
    commercial_price: float = 0
    initial_waste_price: float = 0
    storage_days: int = 0


# =============================================================================
# SWAN FEASIBILITY ANALYZER
# =============================================================================

class SwanFeasibilityAnalyzer:
    """
    SWAN Model Ekonomik Fizibilite Analizi
    
    Formüller:
    1. S_profit = W×P_W + W×CMM_W - (W/C)×FC_T×P_F×D
    2. R_profit = W×P_COM - W×P_W - W×ST_W
    3. P_WBES = CMM_W - (1/C)×FC_T×P_F×D
    4. P_WBER = P_COM - ST_W
    5. Karar: P_WBES < P_WBER → Uygulanabilir ✓
    """
    
    def __init__(self):
        self.name = "SWAN Feasibility Analyzer"
        self.version = "1.0.0"
    
    def analyze(
        self,
        source_facility_id: int,
        receiver_facility_id: int,
        ewc_code: str,
        waste_quantity_ton: float,
        distance_km: float,
        waste_type_id: int = 0,
        source_storage_cost_per_ton: Optional[float] = None,
        receiver_storage_cost_per_ton: Optional[float] = None,
        initial_negotiation_price: Optional[float] = None
    ) -> FeasibilityResult:
        """
        SWAN modeli ile fizibilite analizi yap
        """
        try:
            # ===================================================================
            # 1. VERİ HAZIRLAMASI
            # ===================================================================
            
            cmm_w = get_disposal_savings(ewc_code)
            p_com = get_commercial_price(ewc_code)
            storage_multiplier = get_storage_cost_multiplier(ewc_code)
            
            if source_storage_cost_per_ton is None:
                source_storage_cost_per_ton = DEFAULT_FACILITY_STORAGE_COST * storage_multiplier
            if receiver_storage_cost_per_ton is None:
                receiver_storage_cost_per_ton = DEFAULT_FACILITY_STORAGE_COST * storage_multiplier
            
            # ===================================================================
            # 2. TAŞIMA MALİYETİ HESAPLAMASI
            # ===================================================================
            
            transport_data = calculate_transport_cost(
                waste_quantity_ton=waste_quantity_ton,
                distance_km=distance_km,
                include_driver_wage=True,
                include_maintenance=True
            )
            
            transport_cost_details = TransportCostDetails(
                fuel_cost=transport_data["fuel_cost"],
                driver_wage=transport_data["driver_wage"],
                maintenance=transport_data["maintenance"],
                loading_unloading=transport_data["loading_unloading"],
                num_trucks=transport_data["num_trucks"],
                total_per_ton=transport_data["total_per_ton"],
                total=transport_data["total"]
            )
            
            total_transport_cost = transport_data["total"]
            transport_cost_per_ton = transport_data["total_per_ton"]
            
            # ===================================================================
            # 3. BREAK-EVEN FİYATLARI HESAPLAMASI
            # ===================================================================
            
            # P_WBES: Kaynağın kabul edebileceği minimum fiyat
            p_wbes = max(0, cmm_w - transport_cost_per_ton)
            
            # P_WBER: Alıcının ödeyebileceği maksimum fiyat
            p_wber = max(0, p_com - receiver_storage_cost_per_ton)
            
            # Önerilen fiyat ve pazarlık alanı
            if p_wbes <= p_wber:
                suggested_price = (p_wbes + p_wber) / 2
                negotiation_margin = p_wber - p_wbes
            else:
                suggested_price = (p_wbes + p_wber) / 2
                negotiation_margin = 0
            
            transaction_price = initial_negotiation_price or suggested_price
            
            # ===================================================================
            # 4. KAYNAK TESİS KARI HESAPLAMASI (S_profit)
            # ===================================================================
            
            quantity_revenue = waste_quantity_ton * transaction_price
            disposal_savings_value = waste_quantity_ton * cmm_w
            
            source_total_profit = quantity_revenue + disposal_savings_value - total_transport_cost
            source_profit_per_ton = source_total_profit / waste_quantity_ton if waste_quantity_ton > 0 else 0
            
            source_profit = SourceProfit(
                waste_quantity_ton=waste_quantity_ton,
                sale_price_per_ton=transaction_price,
                quantity_revenue=quantity_revenue,
                disposal_savings=disposal_savings_value,
                transport_cost=total_transport_cost,
                total_profit=source_total_profit,
                profit_per_ton=source_profit_per_ton
            )
            
            # ===================================================================
            # 5. ALICI TESİS KARI HESAPLAMASI (R_profit)
            # ===================================================================
            
            receiver_revenue = waste_quantity_ton * p_com
            receiver_purchase_cost = waste_quantity_ton * transaction_price
            receiver_storage_cost = waste_quantity_ton * receiver_storage_cost_per_ton
            
            receiver_total_profit = receiver_revenue - receiver_purchase_cost - receiver_storage_cost
            receiver_profit_per_ton = receiver_total_profit / waste_quantity_ton if waste_quantity_ton > 0 else 0
            
            receiver_profit = ReceiverProfit(
                waste_quantity_ton=waste_quantity_ton,
                commercial_price_per_ton=p_com,
                purchase_price_per_ton=transaction_price,
                revenue=receiver_revenue,
                purchase_cost=receiver_purchase_cost,
                storage_cost=receiver_storage_cost,
                total_profit=receiver_total_profit,
                profit_per_ton=receiver_profit_per_ton
            )
            
            # ===================================================================
            # 6. KALİTE KARARI VE FİZİBİLİTE SKORU
            # ===================================================================
            
            is_feasible = p_wbes < p_wber
            
            if is_feasible:
                decision_reason = f"Pazarlık alanı var. Min: {p_wbes:.2f} ₺, Max: {p_wber:.2f} ₺"
            else:
                decision_reason = f"Pazarlık alanı YOK. Min ({p_wbes:.2f} ₺) > Max ({p_wber:.2f} ₺)"
            
            # Confidence score (0-100)
            if not is_feasible:
                confidence_score = 0.0
            else:
                source_margin = source_profit_per_ton / transaction_price * 100 if transaction_price > 0 else 0
                receiver_margin = receiver_profit_per_ton / p_com * 100 if p_com > 0 else 0
                both_profitable = min(source_margin, receiver_margin) > 5
                
                negotiations_wide = negotiation_margin > (p_wber * 0.1) if p_wber > 0 else False
                
                if both_profitable and negotiations_wide:
                    confidence_score = 85.0 + min(15.0, (negotiation_margin / suggested_price) * 100 if suggested_price > 0 else 0)
                elif both_profitable:
                    confidence_score = 70.0
                else:
                    confidence_score = 50.0
            
            break_even = BreakEvenAnalysis(
                source_break_even_min=p_wbes,
                receiver_break_even_max=p_wber,
                suggested_price=suggested_price,
                negotiation_margin=max(0, negotiation_margin),
                is_feasible=is_feasible,
                reason=decision_reason
            )
            
            # ===================================================================
            # 7. SONUÇ
            # ===================================================================
            
            result = FeasibilityResult(
                source_facility_id=source_facility_id,
                receiver_facility_id=receiver_facility_id,
                waste_type_id=waste_type_id,
                ewc_code=ewc_code,
                waste_quantity_ton=waste_quantity_ton,
                distance_km=distance_km,
                transport_cost_details=transport_cost_details,
                source_profit=source_profit,
                receiver_profit=receiver_profit,
                break_even=break_even,
                is_feasible=is_feasible,
                decision_reason=decision_reason,
                confidence_score=confidence_score,
                analysis_date=datetime.now()
            )
            
            return result
            
        except Exception as e:
            logger.error(f"SWAN feasibility analysis error: {e}")
            raise


# =============================================================================
# BACKWARD COMPATIBILITY WRAPPER
# =========================================================================== 

class FeasibilityAnalyzer(SwanFeasibilityAnalyzer):
    """Eski API için uyumluluk wrapper"""
    pass
