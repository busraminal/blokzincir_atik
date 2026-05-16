"""
ATIK AI - Web API Kullanım Örneği
==================================

Bu dosya sistemin nasıl web'e bağlanacağını gösterir.
"""

# =============================================================================
# 1. DOĞRUDAN PYTHON KULLANIMI (Backend için)
# =============================================================================

from atik_ai.economics.feasibility import SwanFeasibilityAnalyzer

def analyze_deal(ewc_code: str, quantity_ton: float, distance_km: float) -> dict:
    """
    Tek bir atık transferi için fizibilite analizi
    
    Girdiler:
        ewc_code: EWC atık kodu (örn: "70213")
        quantity_ton: Atık miktarı (ton)
        distance_km: Mesafe (km)
    
    Çıktı: Fizibilite sonuç dict'i
    """
    analyzer = SwanFeasibilityAnalyzer()
    
    result = analyzer.analyze(
        source_facility_id=1,      # Sonra DB'den al
        receiver_facility_id=2,    # Sonra DB'den al
        ewc_code=ewc_code,
        waste_quantity_ton=quantity_ton,
        distance_km=distance_km
    )
    
    return result.to_dict()


# =============================================================================
# 2. FASTAPI SUNUCUSU BAŞLATMA
# =============================================================================

def start_api_server():
    """
    FastAPI sunucusunu başlat
    
    Terminal komutu: uvicorn atik_ai.api.routes:api_router --reload --port 8000
    """
    from fastapi import FastAPI
    from atik_ai.api.routes import api_router
    
    app = FastAPI(
        title="ATIK AI - Döngüsel Ekonomi API",
        description="SWAN Model ile ekonomik fizibilite analizi",
        version="1.0.0"
    )
    
    app.include_router(api_router)
    
    return app


# =============================================================================
# 3. WEB REQUEST ÖRNEKLERİ
# =============================================================================

# POST /api/v1/feasibility/analyze
REQUEST_EXAMPLE = {
    "source_facility_id": 1,
    "receiver_facility_id": 2,
    "waste_type_id": 0,
    "ewc_code": "70213",           # Plastik ambalaj
    "waste_quantity_ton": 45.0,    # 45 ton
    "distance_km": 120.0           # 120 km
}

# Opsiyonel parametreler:
REQUEST_WITH_OPTIONS = {
    "source_facility_id": 1,
    "receiver_facility_id": 2,
    "ewc_code": "200139",          # Karışık plastik
    "waste_quantity_ton": 100.0,
    "distance_km": 80.0,
    "source_storage_cost": 200.0,  # ₺/ton/gün
    "receiver_storage_cost": 150.0,
    "initial_price": 5000.0        # Başlangıç pazarlık fiyatı
}


# =============================================================================
# 4. CURL KOMUTLARI
# =============================================================================

CURL_EXAMPLES = """
# Fizibilite Analizi
curl -X POST "http://localhost:8000/api/v1/feasibility/analyze" \\
  -H "Content-Type: application/json" \\
  -d '{
    "source_facility_id": 1,
    "receiver_facility_id": 2,
    "ewc_code": "70213",
    "waste_quantity_ton": 45.0,
    "distance_km": 120.0
  }'

# Sağlık Kontrolü
curl http://localhost:8000/api/v1/health/
"""


# =============================================================================
# 5. DESTEKLENEN EWC KODLARI
# =============================================================================

from atik_ai.economics.pricing_table import EWC_FEATURES

def list_supported_ewc_codes():
    """Sistemin desteklediği EWC kodlarını listele"""
    print("Desteklenen EWC Kodları:")
    print("-" * 40)
    for code in sorted(EWC_FEATURES.keys()):
        features = EWC_FEATURES[code]
        print(f"  {code} - tehlike: {features['hazard']:.0%}, geri dönüşüm: {features['recyclability']:.0%}")


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ATIK AI - Web API Demo")
    print("=" * 60)
    
    # 1. Doğrudan kullanım
    print("\n1. Doğrudan Python Kullanımı:")
    result = analyze_deal("70213", 45.0, 120.0)
    print(f"   Uygulanabilir: {result['is_feasible']}")
    print(f"   Güven: {result['confidence_score']:.1f}%")
    print(f"   Önerilen Fiyat: {result['break_even']['suggested_price']:.0f} ₺/ton")
    
    # 2. Desteklenen kodlar
    print("\n2. Desteklenen EWC Kodları:")
    list_supported_ewc_codes()
    
    # 3. API başlatma
    print("\n3. API Sunucusu İçin:")
    print("   uvicorn atik_ai.api.routes:api_router --reload --port 8000")
    print("   veya")
    print("   python -m uvicorn atik_ai.api.routes:api_router --reload --port 8000")
