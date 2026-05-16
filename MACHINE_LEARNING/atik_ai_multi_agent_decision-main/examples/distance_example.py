"""
ATIK AI Distance Module - Örnek Kullanım

Bu örnek, mesafe hesaplama sisteminin nasıl kullanılacağını gösterir.
"""
from atik_ai.distance import DistanceCalculator, DistanceCache, DistanceMatrixBuilder
from atik_ai.distance.calculator import DistanceStrategy, Facility

# =============================================================================
# ÖRNEK 1: Basit Mesafe Hesaplama (OSMnx - Ücretsiz)
# =============================================================================

def example_simple_distance():
    """İki nokta arası mesafe hesapla"""
    
    # Calculator oluştur (varsayılan: OSMnx)
    calculator = DistanceCalculator(strategy=DistanceStrategy.OSMNX)
    
    # Ankara -> İstanbul
    ankara = (39.9334, 32.8597)
    istanbul = (41.0082, 28.9784)
    
    result = calculator.calculate(ankara, istanbul)
    
    print(f"📍 Ankara → İstanbul")
    print(f"   Mesafe: {result.distance_km:.1f} km")
    print(f"   Süre: {result.duration_min:.0f} dakika")
    print(f"   Kaynak: {result.source}")


# =============================================================================
# ÖRNEK 2: Lojistik Maliyet Hesaplama (SWAN Formülü)
# =============================================================================

def example_transport_cost():
    """Atık taşıma maliyeti hesapla"""
    
    calculator = DistanceCalculator(strategy=DistanceStrategy.OSMNX)
    
    # Kaynak tesis (Kocaeli) -> Alıcı tesis (Bursa)
    source = (40.7654, 29.9408)  # Kocaeli
    receiver = (40.1885, 29.0610)  # Bursa
    
    # 100 ton atık taşıma maliyeti
    cost = calculator.get_route_cost(
        origin=source,
        destination=receiver,
        weight_ton=100,
        truck_capacity=25.0,      # 25 tonluk kamyon
        fuel_consumption=0.35,    # 0.35 L/km
        fuel_price=42.0           # 42 TL/L
    )
    
    print(f"🚛 Lojistik Maliyet Hesabı")
    print(f"   Mesafe: {cost['distance_km']:.1f} km")
    print(f"   Gereken kamyon: {cost['num_trucks']:.0f} adet")
    print(f"   Toplam maliyet: {cost['transport_cost_tl']:,.0f} TL")
    print(f"   Ton başı maliyet: {cost['cost_per_ton_tl']:.2f} TL/ton")


# =============================================================================
# ÖRNEK 3: Distance Matrix + Cache (KRİTİK STRATEJİ)
# =============================================================================

def example_distance_matrix():
    """
    💡 KRİTİK STRATEJİ:
    - Her mesafeyi API ile hesaplama ❌
    - Önceden hesapla + cache kullan ✅
    """
    
    # Cache oluştur (Redis + Disk fallback)
    cache = DistanceCache(
        redis_host="localhost",
        redis_port=6379,
        disk_cache_dir="./cache/distances"
    )
    
    # Calculator with cache
    calculator = DistanceCalculator(
        strategy=DistanceStrategy.OSMNX,
        cache=cache
    )
    
    # Matrix builder
    builder = DistanceMatrixBuilder(calculator=calculator, cache=cache)
    
    # Tesis listesi
    facilities = [
        Facility("F001", "İstanbul Fabrika", 41.0082, 28.9784),
        Facility("F002", "Ankara Depo", 39.9334, 32.8597),
        Facility("F003", "İzmir Tesis", 38.4192, 27.1287),
        Facility("F004", "Bursa Üretim", 40.1885, 29.0610),
        Facility("F005", "Kocaeli Sanayi", 40.7654, 29.9408),
    ]
    
    # Matrix oluştur (ilk seferde hesaplar, sonra cache'den gelir)
    print("📊 Distance Matrix Oluşturuluyor...")
    matrix = builder.build_matrix(facilities)
    
    print(f"\n✅ Matrix ID: {matrix['matrix_id']}")
    print(f"   Boyut: {matrix['size']}×{matrix['size']}")
    print(f"   Strateji: {matrix['strategy']}")
    
    # En yakın tesisleri bul
    print(f"\n📍 İstanbul'a en yakın tesisler:")
    nearest = builder.find_nearest(matrix, "F001", max_distance_km=500)
    for fac_id, dist in nearest:
        name = matrix['facility_names'][fac_id]
        print(f"   - {name}: {dist:.1f} km")
    
    # Export
    builder.export_matrix(matrix, "distance_matrix.csv")
    print(f"\n📁 Matrix exported: distance_matrix.csv")
    
    # Cache stats
    print(f"\n📈 Cache İstatistikleri:")
    stats = cache.stats()
    print(f"   Redis: {'✅ Bağlı' if stats['redis_connected'] else '❌ Bağlı değil'}")


# =============================================================================
# ÖRNEK 4: OpenRouteService API (Faz 2)
# =============================================================================

def example_ors_api():
    """OpenRouteService ile yüksek doğruluklu mesafe"""
    import os
    
    api_key = os.getenv("ORS_API_KEY")
    if not api_key:
        print("⚠️ ORS_API_KEY tanımlı değil, .env dosyasını kontrol edin")
        return
    
    calculator = DistanceCalculator(
        strategy=DistanceStrategy.ORS,
        config={"ors_api_key": api_key, "ors_profile": "driving-hgv"}
    )
    
    # Kamyon için rota (driving-hgv)
    result = calculator.calculate(
        (41.0082, 28.9784),  # İstanbul
        (39.9334, 32.8597)   # Ankara
    )
    
    print(f"🛣️ ORS API Sonucu")
    print(f"   Mesafe: {result.distance_km:.1f} km")
    print(f"   Süre: {result.duration_min:.0f} dakika")


# =============================================================================
# ÖRNEK 5: Hybrid Yaklaşım (Faz 3 - Production)
# =============================================================================

def example_hybrid():
    """
    Production stratejisi:
    - OSMnx: Bulk hesaplama, matrix oluşturma
    - API: Kritik kararlar, doğrulama
    """
    
    cache = DistanceCache()
    
    # Bulk için OSMnx
    osmnx_calc = DistanceCalculator(
        strategy=DistanceStrategy.OSMNX,
        cache=cache
    )
    
    # Matrix oluştur (OSMnx ile)
    builder = DistanceMatrixBuilder(calculator=osmnx_calc, cache=cache)
    
    # ... matrix oluşturma kodu ...
    
    # Kritik karar için ORS/Google
    # ors_calc = DistanceCalculator(strategy=DistanceStrategy.ORS, ...)
    
    print("🔄 Hybrid strateji aktif")
    print("   Bulk: OSMnx")
    print("   Kritik: API")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ATIK AI - Distance Module Örnekleri")
    print("=" * 60)
    
    # Basit test (Haversine - her zaman çalışır)
    print("\n[TEST] Haversine mesafe hesaplama:")
    from atik_ai.distance.calculator import HaversineProvider
    haversine = HaversineProvider()
    result = haversine.calculate((41.0, 29.0), (40.0, 32.0))
    print(f"   Test sonucu: {result.distance_km:.1f} km")
    
    print("\n" + "=" * 60)
    print("Tam örnekler için fonksiyonları çağırın:")
    print("  example_simple_distance()")
    print("  example_transport_cost()")
    print("  example_distance_matrix()")
    print("=" * 60)
