"""
ATIK AI - Pricing Engine
Break-even fiyat analizi

P_WBES: Kaynağın kabul edebileceği minimum fiyat
P_WBER: Alıcının ödeyebileceği maksimum fiyat

Karar: P_WBES < P_WBER → Eşleşme uygulanabilir
Önerilen Fiyat: (P_WBES + P_WBER) / 2
"""
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

from ..config import config

logger = logging.getLogger(__name__)


@dataclass
class BreakEvenResult:
    """Break-even analiz sonucu"""
    # Fiyatlar
    source_break_even: float      # P_WBES: Kaynak min fiyat
    receiver_break_even: float    # P_WBER: Alıcı max fiyat
    suggested_price: float        # Önerilen fiyat
    price_range: Tuple[float, float]  # (min, max)
    
    # Karar
    is_feasible: bool
    negotiation_margin: float     # P_WBER - P_WBES
    margin_percentage: float      # Yüzdelik marj
    
    # Taraflar için kâr (suggested price ile)
    source_profit_at_suggested: float
    receiver_profit_at_suggested: float
    
    def to_dict(self) -> dict:
        return {
            "source_break_even": self.source_break_even,
            "receiver_break_even": self.receiver_break_even,
            "suggested_price": self.suggested_price,
            "price_range": self.price_range,
            "is_feasible": self.is_feasible,
            "negotiation_margin": self.negotiation_margin,
            "margin_percentage": self.margin_percentage,
            "source_profit_at_suggested": self.source_profit_at_suggested,
            "receiver_profit_at_suggested": self.receiver_profit_at_suggested
        }


class PricingEngine:
    """
    Fiyatlama Motoru
    
    SWAN Break-even formülleri:
    
    P_WBES (Source Break-even):
    Kaynak tesisin kâr = 0 olduğu fiyat
    
    P_WBER (Receiver Break-even):
    Alıcı tesisin kâr = 0 olduğu fiyat
    """
    
    def calculate_source_break_even(
        self,
        waste_quantity: float,       # W (ton)
        disposal_savings: float,     # CMM_W (TL/ton) - mevcut bertaraftan tasarruf
        transport_cost: float,       # Nakliye maliyeti (TL)
    ) -> float:
        """
        Kaynak tesisin kabul edebileceği minimum satış fiyatını hesapla
        
        S_profit = W × P_W + W × CMM_W - Transport_Cost
        
        P_W = 0 olduğunda:
        P_WBES = (Transport_Cost / W) - CMM_W
        
        Negatif çıkarsa 0 olarak al (bertaraf tasarrufu yeterli)
        """
        if waste_quantity <= 0:
            return 0
        
        # P_WBES = (Transport / W) - CMM
        break_even = (transport_cost / waste_quantity) - disposal_savings
        
        # Minimum 0
        return max(0, round(break_even, 2))
    
    def calculate_receiver_break_even(
        self,
        waste_quantity: float,       # W (ton)
        commercial_price: float,     # P_COM (TL/ton) - ticari hammadde fiyatı
        storage_cost: float = 0,     # ST_W (TL/ton) - depolama maliyeti
    ) -> float:
        """
        Alıcı tesisin ödeyebileceği maksimum fiyatı hesapla
        
        R_profit = W × P_COM - W × P_W - W × ST_W
        
        R_profit = 0 olduğunda:
        P_WBER = P_COM - ST_W
        """
        if waste_quantity <= 0:
            return 0
        
        # P_WBER = P_COM - ST_W
        break_even = commercial_price - storage_cost
        
        return max(0, round(break_even, 2))
    
    def analyze_break_even(
        self,
        waste_quantity: float,       # W (ton)
        disposal_savings: float,     # CMM_W (TL/ton)
        transport_cost: float,       # Nakliye maliyeti (TL)
        commercial_price: float,     # P_COM (TL/ton)
        storage_cost: float = 0,     # ST_W (TL/ton)
    ) -> BreakEvenResult:
        """
        Tam break-even analizi
        
        Returns:
            BreakEvenResult
        """
        # Break-even fiyatları
        p_wbes = self.calculate_source_break_even(
            waste_quantity, disposal_savings, transport_cost
        )
        p_wber = self.calculate_receiver_break_even(
            waste_quantity, commercial_price, storage_cost
        )
        
        # Karar: P_WBES < P_WBER
        is_feasible = p_wbes < p_wber
        
        # Müzakere marjı
        negotiation_margin = p_wber - p_wbes
        
        # Yüzdelik marj
        if p_wbes > 0:
            margin_percentage = (negotiation_margin / p_wbes) * 100
        else:
            margin_percentage = 100 if is_feasible else 0
        
        # Önerilen fiyat (ortanca)
        if is_feasible:
            suggested_price = (p_wbes + p_wber) / 2
        else:
            suggested_price = p_wbes  # Kaynağın minimum fiyatı
        
        suggested_price = round(suggested_price, 2)
        
        # Önerilen fiyatta kârlar
        source_profit = (
            waste_quantity * suggested_price +
            waste_quantity * disposal_savings -
            transport_cost
        )
        
        receiver_profit = (
            waste_quantity * commercial_price -
            waste_quantity * suggested_price -
            waste_quantity * storage_cost
        )
        
        return BreakEvenResult(
            source_break_even=p_wbes,
            receiver_break_even=p_wber,
            suggested_price=suggested_price,
            price_range=(p_wbes, p_wber),
            is_feasible=is_feasible,
            negotiation_margin=round(negotiation_margin, 2),
            margin_percentage=round(margin_percentage, 2),
            source_profit_at_suggested=round(source_profit, 2),
            receiver_profit_at_suggested=round(receiver_profit, 2)
        )
    
    def calculate_optimal_price(
        self,
        p_wbes: float,
        p_wber: float,
        source_power: float = 0.5,  # Kaynak pazarlık gücü [0-1]
    ) -> float:
        """
        Tarafların pazarlık gücüne göre optimal fiyat
        
        Args:
            source_power: 1.0 = kaynak tüm marjı alır, 0.0 = alıcı alır
        """
        if p_wbes >= p_wber:
            return p_wbes
        
        margin = p_wber - p_wbes
        optimal = p_wbes + (margin * source_power)
        
        return round(optimal, 2)
    
    def calculate_trade_off(
        self,
        break_even: BreakEvenResult,
        cost_share_source: float = 0.5,  # Kaynağın maliyet payı [0-1]
    ) -> dict:
        """
        Ekonomik olmayan eşleşmeyi uygulanabilir kılmak için
        maliyet paylaşım analizi
        
        Taraflar nakliye veya depolama maliyetlerini paylaşırsa
        eşleşme tekrar değerlendirilir.
        """
        if break_even.is_feasible:
            return {
                "trade_off_needed": False,
                "message": "Eşleşme zaten ekonomik olarak uygulanabilir"
            }
        
        gap = break_even.source_break_even - break_even.receiver_break_even
        
        # Her tarafın karşılaması gereken miktar
        source_contribution = gap * cost_share_source
        receiver_contribution = gap * (1 - cost_share_source)
        
        return {
            "trade_off_needed": True,
            "gap_to_close": round(gap, 2),
            "source_contribution_per_ton": round(source_contribution, 2),
            "receiver_contribution_per_ton": round(receiver_contribution, 2),
            "suggested_new_source_price": round(
                break_even.source_break_even - source_contribution, 2
            ),
            "message": f"Eşleşmeyi uygulanabilir kılmak için ton başına {gap:.2f} TL fark kapatılmalı"
        }
    
    def sensitivity_analysis(
        self,
        base_result: BreakEvenResult,
        waste_quantity: float,
        disposal_savings: float,
        transport_cost: float,
        commercial_price: float,
        storage_cost: float = 0,
        variations: list = None
    ) -> list:
        """
        Parametrelere göre duyarlılık analizi
        
        Args:
            variations: ±% değişim oranları [0.1, 0.2, 0.3]
        """
        variations = variations or [0.1, 0.2, 0.3]
        results = []
        
        for var in variations:
            # Transport cost artışı
            new_transport = transport_cost * (1 + var)
            result_up = self.analyze_break_even(
                waste_quantity, disposal_savings, new_transport,
                commercial_price, storage_cost
            )
            
            results.append({
                "scenario": f"Transport +{var*100:.0f}%",
                "is_feasible": result_up.is_feasible,
                "margin": result_up.negotiation_margin
            })
            
            # Commercial price düşüşü
            new_com = commercial_price * (1 - var)
            result_down = self.analyze_break_even(
                waste_quantity, disposal_savings, transport_cost,
                new_com, storage_cost
            )
            
            results.append({
                "scenario": f"Commercial -{var*100:.0f}%",
                "is_feasible": result_down.is_feasible,
                "margin": result_down.negotiation_margin
            })
        
        return results
