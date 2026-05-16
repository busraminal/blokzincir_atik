#!/usr/bin/env python
"""
ATIK AI - Örnek Kullanım

Bu script sistemin temel özelliklerini gösterir.
"""
import asyncio
from datetime import date


def example_matching():
    """Eşleştirme örneği"""
    print("\n" + "="*60)
    print("EŞLEŞME BULMA ÖRNEĞİ")
    print("="*60)
    
    from atik_ai.matching import MatchingEngine
    
    engine = MatchingEngine()
    
    # Kaynak tesis
    source = {
        "id": 1,
        "name": "ABC Gıda A.Ş.",
        "nace": "10.11",  # Et işleme
        "coords": (41.0082, 28.9784),  # İstanbul
        "ewc_codes": ["02 02 01", "02 02 03"]  # Gıda atıkları
    }
    
    # Potansiyel alıcılar
    receivers = [
        {
            "id": 2,
            "name": "Organik Gübre Ltd.",
            "nace": "20.15",  # Gübre üretimi
            "coords": (41.1, 29.0)
        },
        {
            "id": 3,
            "name": "Biyogaz Enerji A.Ş.",
            "nace": "35.11",  # Elektrik üretimi
            "coords": (40.9, 28.8)
        },
        {
            "id": 4,
            "name": "Hayvan Yemi San.",
            "nace": "10.91",  # Hazır yem
            "coords": (41.2, 29.1)
        }
    ]
    
    # Eşleşme bul
    matches = engine.find_matches(
        source=source,
        receivers=receivers,
        max_results=5
    )
    
    print(f"\nKaynak: {source['name']}")
    print(f"Atık kodları: {source['ewc_codes']}")
    print(f"\nBulunan eşleşmeler: {len(matches)}")
    
    for match in matches:
        print(f"\n  #{match.rank} - Alıcı ID: {match.receiver_id}")
        print(f"     Genel Skor: {match.overall_score:.2%}")
        print(f"     Mesafe: {match.distance_km:.1f} km")
        print(f"     Kalite: {match.match_quality}")


def example_feasibility():
    """Fizibilite analizi örneği"""
    print("\n" + "="*60)
    print("EKONOMİK FİZİBİLİTE ÖRNEĞİ")
    print("="*60)
    
    from atik_ai.economics import FeasibilityAnalyzer, MatchInput
    
    analyzer = FeasibilityAnalyzer()
    
    # Eşleşme parametreleri
    match_input = MatchInput(
        source_facility_id=1,
        receiver_facility_id=2,
        waste_type_id=1,
        waste_quantity_ton=50,  # 50 ton
        source_coords=(41.0082, 28.9784),
        receiver_coords=(41.1, 29.0),
        disposal_savings=80,      # Mevcut bertaraf maliyeti: 80 TL/ton
        commercial_price=120,     # Ticari fiyat: 120 TL/ton
        storage_days=7
    )
    
    result = analyzer.analyze(match_input)
    
    print(f"\nAtık Miktarı: {result.waste_quantity_ton} ton")
    print(f"Mesafe: {result.transport.distance_km:.1f} km")
    print(f"Nakliye Maliyeti: {result.transport.total_cost:,.2f} TL")
    print(f"\nKaynak Tesis Kârı: {result.source_profit:,.2f} TL")
    print(f"Alıcı Tesis Kârı: {result.receiver_profit:,.2f} TL")
    print(f"\nÖnerilen Fiyat: {result.break_even.suggested_price:.2f} TL/ton")
    print(f"Uygulanabilir: {'Evet ✅' if result.is_feasible else 'Hayır ❌'}")
    print(f"\nKarar: {result.decision_reason}")


def example_distance():
    """Mesafe hesaplama örneği"""
    print("\n" + "="*60)
    print("MESAFE HESAPLAMA ÖRNEĞİ")
    print("="*60)
    
    from atik_ai.distance import DistanceCalculator
    from atik_ai.distance.calculator import DistanceStrategy
    
    # Haversine (en hızlı)
    calculator = DistanceCalculator(strategy=DistanceStrategy.HAVERSINE)
    
    # İstanbul - Ankara
    istanbul = (41.0082, 28.9784)
    ankara = (39.9334, 32.8597)
    
    result = calculator.calculate(istanbul, ankara)
    
    print(f"\nİstanbul - Ankara")
    print(f"Mesafe: {result.distance_km:.2f} km")
    print(f"Kaynak: {result.source}")


async def example_agents():
    """Multi-agent örneği"""
    print("\n" + "="*60)
    print("MULTI-AGENT SİSTEMİ ÖRNEĞİ")
    print("="*60)
    
    from atik_ai.agents import AtikAIOrchestrator
    
    orchestrator = AtikAIOrchestrator()
    
    # Sorgu
    query = "Plastik ambalaj atıkları için geri dönüşüm tesisi bul"
    
    print(f"\nSorgu: {query}")
    print("İşleniyor...")
    
    response = orchestrator.run(query)
    
    print(f"\nYanıt:\n{response}")


def example_technical_matching():
    """Teknik eşleşme kuralları örneği"""
    print("\n" + "="*60)
    print("TEKNİK EŞLEŞTİRME KURALLARI ÖRNEĞİ")
    print("="*60)
    
    from atik_ai.matching import TechnicalMatcher
    
    matcher = TechnicalMatcher()
    
    # Test eşleşmeleri
    tests = [
        ("15 01 02", "22.21"),  # Plastik atık -> Plastik üretimi
        ("15 01 01", "17.12"),  # Kağıt atık -> Kağıt üretimi
        ("17 04 01", "24.10"),  # Metal atık -> Metal üretimi
        ("02 02 01", "10.11"),  # Gıda atığı -> Gıda işleme
    ]
    
    print("\nEWC Kodu -> NACE Kodu : Uyumluluk")
    print("-" * 50)
    
    for ewc, nace in tests:
        is_compat, score, rule = matcher.check_compatibility(ewc, nace)
        status = "✅" if is_compat else "❌"
        category = rule.waste_category if rule else "N/A"
        print(f"{ewc} -> {nace} : {status} {score:.0%} ({category})")


def main():
    """Ana fonksiyon"""
    print("\n" + "="*60)
    print("ATIK AI - Demo")
    print("Çoklu Ajanlı Hibrit Karar Destek Sistemi")
    print("="*60)
    
    try:
        # Basit örnekler (senkron)
        example_distance()
        example_technical_matching()
        example_matching()
        example_feasibility()
        
        # Async örnek
        print("\n[Multi-Agent sistemi için async çalıştırma gerekli]")
        # asyncio.run(example_agents())
        
        print("\n" + "="*60)
        print("Demo tamamlandı!")
        print("="*60)
        
    except ImportError as e:
        print(f"\n⚠️ Import hatası: {e}")
        print("Gerekli bağımlılıkları yükleyin: pip install -r requirements.txt")
    except Exception as e:
        print(f"\n❌ Hata: {e}")


if __name__ == "__main__":
    main()
