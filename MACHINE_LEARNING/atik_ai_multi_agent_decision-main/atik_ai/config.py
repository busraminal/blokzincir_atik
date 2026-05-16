"""
ATIK AI Konfigürasyon Yönetimi
"""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()


@dataclass
class DistanceConfig:
    """Mesafe hesaplama konfigürasyonu"""
    
    # Strateji: "osmnx" | "ors" | "google" | "hybrid"
    strategy: str = "osmnx"
    
    # OSMnx ayarları
    osmnx_network_type: str = "drive"  # drive, walk, bike
    osmnx_cache_folder: str = "./cache/osmnx"
    
    # OpenRouteService ayarları
    ors_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ORS_API_KEY"))
    ors_base_url: str = "https://api.openrouteservice.org"
    ors_profile: str = "driving-hgv"  # driving-car, driving-hgv (kamyon)
    
    # Google Maps (opsiyonel, kritik kararlar için)
    google_api_key: Optional[str] = field(default_factory=lambda: os.getenv("GOOGLE_MAPS_API_KEY"))
    
    # Cache ayarları
    use_redis: bool = True
    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_db: int = 0
    redis_password: Optional[str] = field(default_factory=lambda: os.getenv("REDIS_PASSWORD"))
    
    # Disk cache (Redis fallback)
    disk_cache_dir: str = "./cache/distances"
    
    # Cache TTL (saniye) - 30 gün
    cache_ttl: int = 60 * 60 * 24 * 30


@dataclass
class MatchingConfig:
    """Eşleştirme motoru (NACE–EWC, mesafe, zamansal) varsayılanları"""

    max_distance_km: float = 200.0
    min_technical_score: float = 0.0
    min_overall_score: float = 0.0


@dataclass
class EconomicsConfig:
    """Ekonomik fizibilite konfigürasyonu"""
    
    # Varsayılan lojistik parametreleri
    default_truck_capacity_ton: float = 25.0  # C: Kamyon kapasitesi
    default_fuel_consumption_l_km: float = 0.35  # FC_T: Yakıt tüketimi (L/km)
    default_fuel_price_per_l: float = 42.0  # P_F: Yakıt fiyatı (TL/L)
    
    # Depolama maliyeti (zamansal uyumsuzluk durumunda)
    default_storage_cost_per_ton_day: float = 5.0  # ST_W günlük
    
    # Minimum kârlılık eşiği
    min_profit_margin: float = 0.0  # Başabaş üstü kabul


@dataclass
class AtikAIConfig:
    """Ana konfigürasyon sınıfı"""
    
    distance: DistanceConfig = field(default_factory=DistanceConfig)
    economics: EconomicsConfig = field(default_factory=EconomicsConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    
    # Veritabanı
    postgres_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:admin@localhost:5432/postgre_database"
        )
    )
    
    # LLM - Azure OpenAI
    azure_openai_endpoint: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", "")
    )
    azure_openai_api_key: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", "")
    )
    azure_openai_api_version: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    )
    azure_openai_deployment: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_GENERATIVE_MODEL_DEPLOYMENT_NAME", "gpt-5-mini")
    )
    azure_openai_embedding_deployment: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_DEPLOYMENT_NAME", "text-embedding-3-large")
    )
    
    # Fallback: Standard OpenAI
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    
    @property
    def use_azure(self) -> bool:
        """Azure OpenAI kullanılıp kullanılmayacağını belirle"""
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)
    
    def get(self, key: str, default=None):
        """Noktalı notation ile config değeri al"""
        parts = key.split(".")
        obj = self
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                return default
        return obj if obj is not None else default
    
    @classmethod
    def from_env(cls) -> "AtikAIConfig":
        """Ortam değişkenlerinden konfigürasyon oluştur"""
        return cls()


# Global config instance
config = AtikAIConfig.from_env()
