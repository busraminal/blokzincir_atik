"""
ATIK AI Distance Matrix Builder
Önceden hesapla + Cache kullan stratejisi

💡 KRİTİK STRATEJİ:
- Her mesafeyi API ile hesaplama ❌
- Önceden hesapla + cache kullan ✅

Kullanım:
1. Tüm tesislerin koordinatlarını al
2. Distance Matrix oluştur (batch)
3. Redis/Disk'e kaydet
4. Tekrar API çağırma!
"""
import logging
import hashlib
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime
from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

from .calculator import DistanceCalculator, DistanceStrategy
from .cache import DistanceCache

logger = logging.getLogger(__name__)


@dataclass
class Facility:
    """Tesis bilgisi"""
    id: str
    name: str
    latitude: float
    longitude: float
    nace_code: Optional[str] = None
    
    @property
    def coords(self) -> Tuple[float, float]:
        return (self.latitude, self.longitude)


class DistanceMatrixBuilder:
    """
    Mesafe matrisi oluşturucu
    
    Strateji:
    1. Tesisleri veritabanından çek
    2. N×N mesafe matrisi hesapla
    3. Cache'e kaydet
    4. Sonraki sorgularda cache kullan
    """
    
    def __init__(
        self,
        calculator: Optional[DistanceCalculator] = None,
        cache: Optional[DistanceCache] = None
    ):
        self.calculator = calculator or DistanceCalculator(strategy=DistanceStrategy.OSMNX)
        self.cache = cache or DistanceCache()
    
    def build_matrix(
        self,
        facilities: List[Facility],
        matrix_id: Optional[str] = None,
        force_rebuild: bool = False,
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Tesis listesi için distance matrix oluştur
        
        Args:
            facilities: Tesis listesi
            matrix_id: Matris ID (cache key)
            force_rebuild: Cache'i yoksay
            show_progress: Progress bar göster
            
        Returns:
            {
                "matrix_id": str,
                "facilities": List[str],  # facility IDs
                "distances": List[List[float]],  # N×N matrix
                "created_at": str,
                "strategy": str
            }
        """
        n = len(facilities)
        
        # Matrix ID oluştur
        if not matrix_id:
            ids_hash = hashlib.md5(
                ",".join(sorted(f.id for f in facilities)).encode()
            ).hexdigest()[:12]
            matrix_id = f"facilities_{n}_{ids_hash}"
        
        # Cache kontrol
        if not force_rebuild:
            cached = self.cache.get_matrix(matrix_id)
            if cached:
                logger.info(f"Matrix cache hit: {matrix_id}")
                return cached
        
        logger.info(f"Distance matrix oluşturuluyor: {n}×{n} = {n*n} hesaplama")
        
        # Koordinat listesi
        coords = [f.coords for f in facilities]
        
        # Matris hesapla
        if hasattr(self.calculator._get_provider(self.calculator.strategy), 'calculate_matrix'):
            # Provider matrix desteği varsa kullan (daha hızlı)
            try:
                matrix = self.calculator.calculate_matrix(coords, coords)
                logger.info("Matrix tek seferde hesaplandı")
            except Exception as e:
                logger.warning(f"Batch matrix hatası: {e}, tekil hesaplamaya geç")
                matrix = self._calculate_pairwise(coords, show_progress)
        else:
            matrix = self._calculate_pairwise(coords, show_progress)
        
        # Sonuç hazırla
        result = {
            "matrix_id": matrix_id,
            "facilities": [f.id for f in facilities],
            "facility_names": {f.id: f.name for f in facilities},
            "distances": matrix.tolist(),
            "created_at": datetime.now().isoformat(),
            "strategy": self.calculator.strategy.value,
            "size": n
        }
        
        # Cache'e kaydet
        self.cache.set_matrix(matrix_id, result)
        logger.info(f"Matrix cache'e kaydedildi: {matrix_id}")
        
        return result
    
    def _calculate_pairwise(
        self,
        coords: List[Tuple[float, float]],
        show_progress: bool = True
    ) -> np.ndarray:
        """İkili mesafe hesaplama (yavaş ama her zaman çalışır)"""
        n = len(coords)
        matrix = np.zeros((n, n))
        
        total = n * (n - 1) // 2  # Üst üçgen
        
        iterator = range(n)
        if show_progress:
            iterator = tqdm(iterator, desc="Mesafe hesaplanıyor", total=n)
        
        for i in iterator:
            for j in range(i + 1, n):
                result = self.calculator.calculate(
                    coords[i],
                    coords[j],
                    use_cache=True
                )
                matrix[i, j] = result.distance_km
                matrix[j, i] = result.distance_km  # Simetrik
        
        return matrix
    
    def get_distance(
        self,
        matrix_data: Dict,
        from_id: str,
        to_id: str
    ) -> Optional[float]:
        """Matrix'ten mesafe al"""
        facilities = matrix_data.get("facilities", [])
        distances = matrix_data.get("distances", [])
        
        try:
            i = facilities.index(from_id)
            j = facilities.index(to_id)
            return distances[i][j]
        except (ValueError, IndexError):
            return None
    
    def find_nearest(
        self,
        matrix_data: Dict,
        from_id: str,
        max_distance_km: float = float('inf'),
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """En yakın tesisleri bul"""
        facilities = matrix_data.get("facilities", [])
        distances = matrix_data.get("distances", [])
        names = matrix_data.get("facility_names", {})
        
        try:
            i = facilities.index(from_id)
        except ValueError:
            return []
        
        # Mesafeleri sırala
        pairs = []
        for j, fac_id in enumerate(facilities):
            if i != j and distances[i][j] <= max_distance_km:
                pairs.append((fac_id, distances[i][j], names.get(fac_id, fac_id)))
        
        pairs.sort(key=lambda x: x[1])
        
        return [(p[0], p[1]) for p in pairs[:limit]]
    
    def build_from_database(
        self,
        db_engine,
        table_name: str = "facilities",
        id_column: str = "id",
        name_column: str = "name",
        lat_column: str = "latitude",
        lon_column: str = "longitude",
        nace_column: Optional[str] = "nace_code",
        where_clause: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Veritabanından tesis çekip matrix oluştur
        
        Args:
            db_engine: SQLAlchemy engine
            table_name: Tesis tablosu
            
        Returns:
            Distance matrix
        """
        import pandas as pd
        from sqlalchemy import text
        
        # Query oluştur
        cols = [id_column, name_column, lat_column, lon_column]
        if nace_column:
            cols.append(nace_column)
        
        query = f"SELECT {', '.join(cols)} FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        # Veri çek
        df = pd.read_sql(text(query), db_engine)
        
        # Facility listesi oluştur
        facilities = []
        for _, row in df.iterrows():
            facilities.append(Facility(
                id=str(row[id_column]),
                name=str(row[name_column]),
                latitude=float(row[lat_column]),
                longitude=float(row[lon_column]),
                nace_code=str(row.get(nace_column, "")) if nace_column else None
            ))
        
        logger.info(f"Veritabanından {len(facilities)} tesis yüklendi")
        
        return self.build_matrix(facilities)
    
    def export_matrix(
        self,
        matrix_data: Dict,
        output_path: str,
        format: str = "csv"
    ) -> str:
        """Matrix'i dosyaya export et"""
        import pandas as pd
        
        facilities = matrix_data.get("facilities", [])
        names = matrix_data.get("facility_names", {})
        distances = matrix_data.get("distances", [])
        
        # DataFrame oluştur
        labels = [names.get(f, f) for f in facilities]
        df = pd.DataFrame(distances, index=labels, columns=labels)
        
        if format == "csv":
            df.to_csv(output_path)
        elif format == "excel":
            df.to_excel(output_path)
        elif format == "json":
            df.to_json(output_path)
        
        logger.info(f"Matrix export edildi: {output_path}")
        return output_path


# CLI için yardımcı fonksiyon
def build_matrix_cli(
    facilities_csv: str,
    output_path: str = "distance_matrix.csv",
    strategy: str = "osmnx",
    redis_host: str = "localhost"
):
    """
    CLI'dan matrix oluştur
    
    Kullanım:
        python -m atik_ai.distance.matrix facilities.csv --output matrix.csv
    """
    import pandas as pd
    
    # CSV'den facility yükle
    df = pd.read_csv(facilities_csv)
    
    facilities = []
    for _, row in df.iterrows():
        facilities.append(Facility(
            id=str(row.get('id', row.name)),
            name=str(row.get('name', f"Facility_{row.name}")),
            latitude=float(row['latitude']),
            longitude=float(row['longitude'])
        ))
    
    # Calculator ve cache oluştur
    cache = DistanceCache(redis_host=redis_host)
    calculator = DistanceCalculator(
        strategy=DistanceStrategy(strategy),
        cache=cache
    )
    
    # Matrix oluştur
    builder = DistanceMatrixBuilder(calculator=calculator, cache=cache)
    matrix = builder.build_matrix(facilities)
    
    # Export
    builder.export_matrix(matrix, output_path)
    
    print(f"✅ Matrix oluşturuldu: {len(facilities)}×{len(facilities)}")
    print(f"📁 Çıktı: {output_path}")
    
    return matrix


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Distance Matrix Builder")
    parser.add_argument("facilities_csv", help="Tesis listesi CSV")
    parser.add_argument("--output", "-o", default="distance_matrix.csv")
    parser.add_argument("--strategy", "-s", default="osmnx", choices=["osmnx", "ors", "haversine"])
    parser.add_argument("--redis-host", default="localhost")
    
    args = parser.parse_args()
    
    build_matrix_cli(
        args.facilities_csv,
        args.output,
        args.strategy,
        args.redis_host
    )
