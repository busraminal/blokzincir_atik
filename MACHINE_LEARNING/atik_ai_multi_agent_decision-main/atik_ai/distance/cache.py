"""
ATIK AI Distance Cache
Redis + Disk hibrit cache sistemi

Strateji:
1. Distance Matrix önceden hesapla
2. Redis'e kaydet
3. Tekrar API çağırma!
"""
import json
import hashlib
import logging
from typing import Optional, Tuple
from dataclasses import asdict

logger = logging.getLogger(__name__)


class DistanceCache:
    """
    Hibrit distance cache sistemi
    
    Öncelik:
    1. Redis (hızlı, distributed)
    2. DiskCache (fallback, persistent)
    """
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        disk_cache_dir: str = "./cache/distances",
        ttl: int = 60 * 60 * 24 * 30,  # 30 gün
        use_redis: bool = True
    ):
        self.ttl = ttl
        self.use_redis = use_redis
        
        # Redis bağlantısı
        self._redis = None
        if use_redis:
            try:
                import redis
                self._redis = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                # Bağlantı testi
                self._redis.ping()
                logger.info(f"Redis bağlantısı başarılı: {redis_host}:{redis_port}")
            except Exception as e:
                logger.warning(f"Redis bağlantı hatası: {e}, DiskCache kullanılacak")
                self._redis = None
        
        # Disk cache (fallback)
        self._disk_cache = None
        try:
            from diskcache import Cache
            self._disk_cache = Cache(disk_cache_dir)
            logger.info(f"DiskCache hazır: {disk_cache_dir}")
        except ImportError:
            logger.warning("diskcache yüklü değil")
    
    def _make_key(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> str:
        """Koordinatlardan unique cache key oluştur"""
        # 4 decimal hassasiyet (~11 metre)
        key_str = f"{origin[0]:.4f},{origin[1]:.4f}:{destination[0]:.4f},{destination[1]:.4f}"
        return f"dist:{hashlib.md5(key_str.encode()).hexdigest()}"
    
    def get(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float]
    ) -> Optional["DistanceResult"]:
        """Cache'den mesafe al"""
        from .calculator import DistanceResult
        
        key = self._make_key(origin, destination)
        data = None
        
        # Redis'ten dene
        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    logger.debug(f"Redis cache hit: {key}")
            except Exception as e:
                logger.warning(f"Redis get hatası: {e}")
        
        # Disk cache'ten dene
        if data is None and self._disk_cache:
            try:
                data = self._disk_cache.get(key)
                if data:
                    logger.debug(f"Disk cache hit: {key}")
            except Exception as e:
                logger.warning(f"Disk cache get hatası: {e}")
        
        # Deserialize
        if data:
            try:
                obj = json.loads(data) if isinstance(data, str) else data
                return DistanceResult(**obj)
            except Exception as e:
                logger.warning(f"Cache deserialize hatası: {e}")
        
        return None
    
    def set(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        result: "DistanceResult"
    ) -> bool:
        """Cache'e mesafe kaydet"""
        key = self._make_key(origin, destination)
        
        # Serialize
        data = json.dumps({
            "distance_km": result.distance_km,
            "duration_min": result.duration_min,
            "source": result.source
        })
        
        success = False
        
        # Redis'e kaydet
        if self._redis:
            try:
                self._redis.setex(key, self.ttl, data)
                success = True
                logger.debug(f"Redis cache set: {key}")
            except Exception as e:
                logger.warning(f"Redis set hatası: {e}")
        
        # Disk cache'e kaydet (backup)
        if self._disk_cache:
            try:
                self._disk_cache.set(key, data, expire=self.ttl)
                success = True
                logger.debug(f"Disk cache set: {key}")
            except Exception as e:
                logger.warning(f"Disk cache set hatası: {e}")
        
        return success
    
    def get_matrix(self, matrix_id: str) -> Optional[dict]:
        """Önceden hesaplanmış distance matrix al"""
        key = f"matrix:{matrix_id}"
        
        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis matrix get hatası: {e}")
        
        if self._disk_cache:
            try:
                data = self._disk_cache.get(key)
                if data:
                    return json.loads(data) if isinstance(data, str) else data
            except Exception as e:
                logger.warning(f"Disk matrix get hatası: {e}")
        
        return None
    
    def set_matrix(
        self,
        matrix_id: str,
        matrix_data: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """Distance matrix kaydet"""
        key = f"matrix:{matrix_id}"
        ttl = ttl or self.ttl
        
        data = json.dumps(matrix_data)
        success = False
        
        if self._redis:
            try:
                self._redis.setex(key, ttl, data)
                success = True
            except Exception as e:
                logger.warning(f"Redis matrix set hatası: {e}")
        
        if self._disk_cache:
            try:
                self._disk_cache.set(key, data, expire=ttl)
                success = True
            except Exception as e:
                logger.warning(f"Disk matrix set hatası: {e}")
        
        return success
    
    def stats(self) -> dict:
        """Cache istatistikleri"""
        stats = {
            "redis_connected": self._redis is not None,
            "disk_cache_dir": str(self._disk_cache.directory) if self._disk_cache else None
        }
        
        if self._redis:
            try:
                info = self._redis.info("keyspace")
                stats["redis_keys"] = info.get("db0", {}).get("keys", 0)
            except:
                pass
        
        if self._disk_cache:
            try:
                stats["disk_cache_size_mb"] = self._disk_cache.volume() / (1024 * 1024)
            except:
                pass
        
        return stats
    
    def clear(self, pattern: str = "dist:*") -> int:
        """Cache temizle"""
        deleted = 0
        
        if self._redis:
            try:
                keys = self._redis.keys(pattern)
                if keys:
                    deleted += self._redis.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis clear hatası: {e}")
        
        if self._disk_cache:
            try:
                self._disk_cache.clear()
                logger.info("Disk cache temizlendi")
            except Exception as e:
                logger.warning(f"Disk clear hatası: {e}")
        
        return deleted
