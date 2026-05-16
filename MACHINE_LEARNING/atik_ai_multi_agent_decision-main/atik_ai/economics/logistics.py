"""
ATIK AI - Logistics Calculator
Lojistik maliyet hesaplama

Maliyet = (W/C) × FC_T × P_F × D
"""
import logging
from typing import Tuple, Optional
from dataclasses import dataclass
from decimal import Decimal
import math

from ..distance import DistanceCalculator, DistanceCache
from ..distance.calculator import DistanceStrategy
from ..config import config

logger = logging.getLogger(__name__)


@dataclass
class TransportCost:
    """Nakliye maliyeti sonucu"""
    distance_km: float
    duration_min: float
    num_trucks: int
    total_cost: float          # Toplam maliyet (TL)
    cost_per_ton: float        # Ton başı maliyet (TL/ton)
    fuel_cost: float           # Yakıt maliyeti
    cost_details: dict = None
    
    def to_dict(self) -> dict:
        return {
            "distance_km": self.distance_km,
            "duration_min": self.duration_min,
            "num_trucks": self.num_trucks,
            "total_cost": self.total_cost,
            "cost_per_ton": self.cost_per_ton,
            "fuel_cost": self.fuel_cost,
            "details": self.cost_details or {}
        }


class LogisticsCalculator:
    """
    Lojistik Maliyet Hesaplayıcı
    
    SWAN formülü:
    Transport Cost = (W/C) × FC_T × P_F × D
    
    Parametreler:
    - W: Atık miktarı (ton)
    - C: Kamyon kapasitesi (ton)
    - FC_T: Yakıt tüketimi (L/km)
    - P_F: Yakıt fiyatı (TL/L)
    - D: Mesafe (km)
    """
    
    def __init__(
        self,
        truck_capacity: float = None,
        fuel_consumption: float = None,
        fuel_price: float = None,
        distance_calculator: DistanceCalculator = None
    ):
        # Varsayılan değerler config'den
        self.truck_capacity = truck_capacity or config.economics.default_truck_capacity_ton
        self.fuel_consumption = fuel_consumption or config.economics.default_fuel_consumption_l_km
        self.fuel_price = fuel_price or config.economics.default_fuel_price_per_l
        
        # Distance calculator
        self._distance_calc = distance_calculator
    
    @property
    def distance_calculator(self) -> DistanceCalculator:
        """Lazy distance calculator"""
        if self._distance_calc is None:
            cache = DistanceCache()
            self._distance_calc = DistanceCalculator(
                strategy=DistanceStrategy.OSMNX,
                cache=cache
            )
        return self._distance_calc
    
    def calculate_transport_cost(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        weight_ton: float,
        truck_capacity: float = None,
        fuel_consumption: float = None,
        fuel_price: float = None,
        include_return: bool = True
    ) -> TransportCost:
        """
        Nakliye maliyeti hesapla
        
        Args:
            origin: Kaynak koordinatları (lat, lon)
            destination: Hedef koordinatları (lat, lon)
            weight_ton: Atık miktarı (ton)
            truck_capacity: Kamyon kapasitesi (ton)
            fuel_consumption: Yakıt tüketimi (L/km)
            fuel_price: Yakıt fiyatı (TL/L)
            include_return: Dönüş maliyetini dahil et
            
        Returns:
            TransportCost
        """
        # Parametreler
        C = truck_capacity or self.truck_capacity
        FC_T = fuel_consumption or self.fuel_consumption
        P_F = fuel_price or self.fuel_price
        W = weight_ton
        
        # Mesafe hesapla
        distance_result = self.distance_calculator.calculate(origin, destination)
        D = distance_result.distance_km
        
        # Dönüş dahilse mesafeyi iki katına çıkar
        if include_return:
            D = D * 2
        
        # Gereken kamyon sayısı
        num_trucks = math.ceil(W / C)
        
        # SWAN formülü
        # Transport Cost = (W/C) × FC_T × P_F × D
        # Gerçekte: num_trucks × FC_T × P_F × D
        fuel_cost = num_trucks * FC_T * P_F * D
        
        # Toplam maliyet (yakıt + diğer maliyetler)
        # Diğer maliyetler: sürücü, amortisman, vb. (%30 ekstra)
        other_costs_ratio = 0.3
        total_cost = fuel_cost * (1 + other_costs_ratio)
        
        # Ton başı maliyet
        cost_per_ton = total_cost / W if W > 0 else 0
        
        return TransportCost(
            distance_km=D / (2 if include_return else 1),  # Tek yön mesafe
            duration_min=distance_result.duration_min or 0,
            num_trucks=num_trucks,
            total_cost=round(total_cost, 2),
            cost_per_ton=round(cost_per_ton, 2),
            fuel_cost=round(fuel_cost, 2),
            cost_details={
                "truck_capacity_ton": C,
                "fuel_consumption_l_km": FC_T,
                "fuel_price_tl_l": P_F,
                "include_return": include_return,
                "other_costs_ratio": other_costs_ratio,
                "distance_source": distance_result.source
            }
        )
    
    def calculate_by_facility_ids(
        self,
        source_facility,  # Facility model
        receiver_facility,  # Facility model
        weight_ton: float
    ) -> TransportCost:
        """Tesis objeleri ile hesapla"""
        if not source_facility.coords or not receiver_facility.coords:
            raise ValueError("Tesis koordinatları eksik")
        
        return self.calculate_transport_cost(
            origin=source_facility.coords,
            destination=receiver_facility.coords,
            weight_ton=weight_ton
        )
    
    def estimate_max_distance(
        self,
        budget: float,
        weight_ton: float,
        truck_capacity: float = None,
        fuel_consumption: float = None,
        fuel_price: float = None
    ) -> float:
        """
        Bütçe ile ulaşılabilecek maksimum mesafeyi hesapla
        
        Args:
            budget: Maksimum nakliye bütçesi (TL)
            weight_ton: Atık miktarı (ton)
            
        Returns:
            Maksimum mesafe (km)
        """
        C = truck_capacity or self.truck_capacity
        FC_T = fuel_consumption or self.fuel_consumption
        P_F = fuel_price or self.fuel_price
        
        num_trucks = math.ceil(weight_ton / C)
        
        # D = budget / (num_trucks × FC_T × P_F × 1.3)  # 1.3 = diğer maliyetler
        max_distance = budget / (num_trucks * FC_T * P_F * 1.3 * 2)  # 2 = gidiş-dönüş
        
        return round(max_distance, 2)
    
    def compare_routes(
        self,
        origin: Tuple[float, float],
        destinations: list,  # [(name, lat, lon)]
        weight_ton: float
    ) -> list:
        """Farklı rotaları karşılaştır"""
        results = []
        
        for name, lat, lon in destinations:
            cost = self.calculate_transport_cost(
                origin=origin,
                destination=(lat, lon),
                weight_ton=weight_ton
            )
            results.append({
                "destination": name,
                "distance_km": cost.distance_km,
                "total_cost": cost.total_cost,
                "cost_per_ton": cost.cost_per_ton
            })
        
        # Maliyete göre sırala
        results.sort(key=lambda x: x["total_cost"])
        
        return results
