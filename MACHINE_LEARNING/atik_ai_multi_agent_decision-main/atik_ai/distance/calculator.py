"""
ATIK AI Distance Calculator
Hibrit mesafe hesaplama modülü

Strateji:
- Faz 1 (MVP): OSMnx + NetworkX (ücretsiz, offline)
- Faz 2 (Scaling): OpenRouteService API (ücretsiz, online)
- Faz 3 (Production): Hybrid yaklaşım
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


class DistanceStrategy(Enum):
    """Mesafe hesaplama stratejileri"""
    OSMNX = "osmnx"           # Faz 1: Ücretsiz, offline
    ORS = "ors"               # Faz 2: OpenRouteService API
    GOOGLE = "google"         # Faz 3: Google Maps (kritik kararlar)
    HYBRID = "hybrid"         # Faz 3: OSMnx bulk + API kritik
    HAVERSINE = "haversine"   # Fallback: Kuş uçuşu


@dataclass
class DistanceResult:
    """Mesafe hesaplama sonucu"""
    distance_km: float                    # Gerçek yol mesafesi (D)
    duration_min: Optional[float] = None  # Tahmini süre
    source: str = "unknown"               # Hangi kaynak kullanıldı
    geometry: Optional[List] = None       # Rota koordinatları
    cached: bool = False                  # Cache'den mi geldi
    
    @property
    def distance_m(self) -> float:
        return self.distance_km * 1000


class BaseDistanceProvider(ABC):
    """Mesafe sağlayıcı abstract class"""
    
    @abstractmethod
    def calculate(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> DistanceResult:
        """İki nokta arası mesafe hesapla"""
        pass
    
    @abstractmethod
    def calculate_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]]
    ) -> np.ndarray:
        """Mesafe matrisi hesapla"""
        pass


class HaversineProvider(BaseDistanceProvider):
    """
    Kuş uçuşu mesafe hesaplama (fallback)
    Gerçek yol mesafesi için ~1.3x çarpan uygulanır
    """
    EARTH_RADIUS_KM = 6371
    ROAD_FACTOR = 1.3  # Kuş uçuşu -> yol mesafesi çarpanı
    
    def calculate(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> DistanceResult:
        lat1, lon1 = np.radians(origin)
        lat2, lon2 = np.radians(destination)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        distance = self.EARTH_RADIUS_KM * c * self.ROAD_FACTOR
        
        return DistanceResult(
            distance_km=distance,
            duration_min=distance / 60,  # ~60 km/h ortalama
            source="haversine"
        )
    
    def calculate_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]]
    ) -> np.ndarray:
        matrix = np.zeros((len(origins), len(destinations)))
        
        for i, origin in enumerate(origins):
            for j, dest in enumerate(destinations):
                result = self.calculate(origin, dest)
                matrix[i, j] = result.distance_km
        
        return matrix


class OSMnxProvider(BaseDistanceProvider):
    """
    Faz 1: OSMnx ile gerçek yol mesafesi
    ✅ Tamamen ücretsiz
    ✅ Offline çalışabilir
    ✅ Bulk hesaplama için ideal
    """
    
    def __init__(self, network_type: str = "drive", cache_folder: str = "./cache/osmnx"):
        self.network_type = network_type
        self.cache_folder = cache_folder
        self._graph_cache: Dict[str, Any] = {}
        
        # OSMnx import (lazy)
        try:
            import osmnx as ox
            ox.settings.cache_folder = cache_folder
            ox.settings.use_cache = True
            self.ox = ox
        except ImportError:
            logger.warning("OSMnx yüklü değil. pip install osmnx")
            self.ox = None
    
    def _get_graph(self, center: Tuple[float, float], dist: int = 50000) -> Any:
        """Belirli bir nokta etrafındaki yol ağını al (cache'li)"""
        cache_key = f"{center[0]:.2f}_{center[1]:.2f}_{dist}"
        
        if cache_key not in self._graph_cache:
            logger.info(f"OSMnx: Yol ağı indiriliyor: {center}")
            self._graph_cache[cache_key] = self.ox.graph_from_point(
                center, 
                dist=dist,
                network_type=self.network_type
            )
        
        return self._graph_cache[cache_key]
    
    def calculate(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> DistanceResult:
        if self.ox is None:
            return HaversineProvider().calculate(origin, destination)
        
        try:
            import networkx as nx
            
            # Merkez nokta ve mesafe
            center_lat = (origin[0] + destination[0]) / 2
            center_lon = (origin[1] + destination[1]) / 2
            
            # Haversine ile tahmini mesafe -> buffer olarak kullan
            haversine_dist = HaversineProvider().calculate(origin, destination).distance_km
            buffer_dist = max(int(haversine_dist * 1000 * 1.5), 5000)
            
            # Yol ağını al
            G = self._get_graph((center_lat, center_lon), buffer_dist)
            
            # En yakın düğümleri bul
            orig_node = self.ox.nearest_nodes(G, origin[1], origin[0])
            dest_node = self.ox.nearest_nodes(G, destination[1], destination[0])
            
            # En kısa yolu hesapla
            route = nx.shortest_path(G, orig_node, dest_node, weight="length")
            route_length = nx.shortest_path_length(G, orig_node, dest_node, weight="length")
            
            distance_km = route_length / 1000
            
            # Tahmini süre (ortalama 50 km/h)
            duration_min = (distance_km / 50) * 60
            
            return DistanceResult(
                distance_km=distance_km,
                duration_min=duration_min,
                source="osmnx",
                geometry=[(G.nodes[n]['y'], G.nodes[n]['x']) for n in route]
            )
            
        except Exception as e:
            logger.warning(f"OSMnx hatası: {e}, Haversine'e fallback")
            return HaversineProvider().calculate(origin, destination)
    
    def calculate_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]]
    ) -> np.ndarray:
        """Bulk mesafe matrisi hesaplama"""
        matrix = np.zeros((len(origins), len(destinations)))
        
        for i, origin in enumerate(origins):
            for j, dest in enumerate(destinations):
                result = self.calculate(origin, dest)
                matrix[i, j] = result.distance_km
                
        return matrix


class ORSProvider(BaseDistanceProvider):
    """
    Faz 2: OpenRouteService API
    ✅ Ücretsiz (2500 istek/gün)
    ✅ Yüksek doğruluk
    ✅ Distance matrix API mevcut
    """
    
    def __init__(self, api_key: str, profile: str = "driving-hgv"):
        self.api_key = api_key
        self.profile = profile  # driving-car, driving-hgv (kamyon)
        
        try:
            import openrouteservice
            self.client = openrouteservice.Client(key=api_key)
        except ImportError:
            logger.warning("openrouteservice yüklü değil")
            self.client = None
    
    def calculate(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> DistanceResult:
        if self.client is None:
            return HaversineProvider().calculate(origin, destination)
        
        try:
            # ORS koordinat formatı: [lon, lat]
            coords = [
                [origin[1], origin[0]],
                [destination[1], destination[0]]
            ]
            
            route = self.client.directions(
                coordinates=coords,
                profile=self.profile,
                format="geojson"
            )
            
            props = route["features"][0]["properties"]["summary"]
            
            return DistanceResult(
                distance_km=props["distance"] / 1000,
                duration_min=props["duration"] / 60,
                source="ors",
                geometry=route["features"][0]["geometry"]["coordinates"]
            )
            
        except Exception as e:
            logger.warning(f"ORS hatası: {e}, Haversine'e fallback")
            return HaversineProvider().calculate(origin, destination)
    
    def calculate_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]]
    ) -> np.ndarray:
        """ORS Distance Matrix API kullan"""
        if self.client is None:
            return HaversineProvider().calculate_matrix(origins, destinations)
        
        try:
            # Tüm noktaları birleştir
            all_coords = []
            for lat, lon in origins:
                all_coords.append([lon, lat])
            for lat, lon in destinations:
                all_coords.append([lon, lat])
            
            sources = list(range(len(origins)))
            destinations_idx = list(range(len(origins), len(all_coords)))
            
            result = self.client.distance_matrix(
                locations=all_coords,
                profile=self.profile,
                sources=sources,
                destinations=destinations_idx,
                metrics=["distance"]
            )
            
            # Mesafeyi km'ye çevir
            matrix = np.array(result["distances"]) / 1000
            return matrix
            
        except Exception as e:
            logger.warning(f"ORS Matrix hatası: {e}")
            return HaversineProvider().calculate_matrix(origins, destinations)


class DistanceCalculator:
    """
    Ana mesafe hesaplama sınıfı
    Cache entegrasyonu ile çalışır
    """
    
    def __init__(
        self,
        strategy: DistanceStrategy = DistanceStrategy.OSMNX,
        cache: Optional["DistanceCache"] = None,
        config: Optional[dict] = None
    ):
        self.strategy = strategy
        self.cache = cache
        self.config = config or {}
        
        # Provider'ları lazy yükle
        self._providers: Dict[DistanceStrategy, BaseDistanceProvider] = {}
    
    def _get_provider(self, strategy: DistanceStrategy) -> BaseDistanceProvider:
        """Provider al veya oluştur"""
        if strategy not in self._providers:
            if strategy == DistanceStrategy.HAVERSINE:
                self._providers[strategy] = HaversineProvider()
            
            elif strategy == DistanceStrategy.OSMNX:
                self._providers[strategy] = OSMnxProvider(
                    network_type=self.config.get("network_type", "drive"),
                    cache_folder=self.config.get("osmnx_cache", "./cache/osmnx")
                )
            
            elif strategy == DistanceStrategy.ORS:
                api_key = self.config.get("ors_api_key")
                if not api_key:
                    logger.warning("ORS API key yok, OSMnx'e fallback")
                    return self._get_provider(DistanceStrategy.OSMNX)
                self._providers[strategy] = ORSProvider(
                    api_key=api_key,
                    profile=self.config.get("ors_profile", "driving-hgv")
                )
            
            else:
                self._providers[strategy] = HaversineProvider()
        
        return self._providers[strategy]
    
    def calculate(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        use_cache: bool = True
    ) -> DistanceResult:
        """
        İki nokta arası mesafe hesapla
        
        Args:
            origin: (lat, lon) başlangıç koordinatları
            destination: (lat, lon) bitiş koordinatları
            use_cache: Cache kullan
            
        Returns:
            DistanceResult
        """
        # Cache kontrol
        if use_cache and self.cache:
            cached = self.cache.get(origin, destination)
            if cached:
                cached.cached = True
                return cached
        
        # Hesapla
        provider = self._get_provider(self.strategy)
        result = provider.calculate(origin, destination)
        
        # Cache'e kaydet
        if use_cache and self.cache:
            self.cache.set(origin, destination, result)
        
        return result
    
    def calculate_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]]
    ) -> np.ndarray:
        """Mesafe matrisi hesapla"""
        provider = self._get_provider(self.strategy)
        return provider.calculate_matrix(origins, destinations)
    
    def get_route_cost(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        weight_ton: float,
        truck_capacity: float = 25.0,
        fuel_consumption: float = 0.35,  # L/km
        fuel_price: float = 42.0  # TL/L
    ) -> Dict[str, float]:
        """
        Lojistik maliyet hesapla (SWAN formülü)
        
        Maliyet = (W/C) × FC_T × P_F × D
        
        Args:
            origin: Başlangıç koordinatları
            destination: Bitiş koordinatları
            weight_ton: Atık miktarı (ton)
            truck_capacity: Kamyon kapasitesi (ton)
            fuel_consumption: Yakıt tüketimi (L/km)
            fuel_price: Yakıt fiyatı (TL/L)
            
        Returns:
            Maliyet detayları
        """
        result = self.calculate(origin, destination)
        distance_km = result.distance_km
        
        # Gereken kamyon sayısı
        num_trucks = np.ceil(weight_ton / truck_capacity)
        
        # Toplam maliyet
        transport_cost = num_trucks * fuel_consumption * fuel_price * distance_km
        
        return {
            "distance_km": distance_km,
            "duration_min": result.duration_min,
            "num_trucks": num_trucks,
            "transport_cost_tl": transport_cost,
            "cost_per_ton_tl": transport_cost / weight_ton if weight_ton > 0 else 0,
            "source": result.source
        }
