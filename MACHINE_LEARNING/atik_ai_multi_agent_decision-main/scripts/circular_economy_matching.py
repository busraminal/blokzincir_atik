"""
ATIK AI - Circular Economy Matching Engine
Atık sahipleri (suppliers) ve hammadde ihtiyaç duyanlar (buyers) eşleştir
"""
import json
from sqlalchemy import create_engine, text
from datetime import datetime

engine = create_engine('postgresql://postgres:admin@localhost:5432/postgre_database')

print("\n" + "="*80)
print("CIRCULAR ECONOMY MATCHING ENGINE")
print("="*80)
print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Atık-Hammadde Eşleştirmesi Başladı\n")

# ============================================================================
# 1. ATIK SAHİPLERİNİ AL (waste_predictions'dan)
# ============================================================================
print("[1] Atık Sahipleri Taranıyor...")
with engine.connect() as conn:
    waste_suppliers = conn.execute(text("""
        SELECT DISTINCT
            f.id as supplier_id,
            f.facility_name,
            f.city,
            wp.waste_code,
            wp.waste_name,
            wp.estimated_ton as available_ton,
            wp.confidence,
            wp.explanation
        FROM facility_waste_predictions wp
        JOIN facilities f ON wp.facility_id = f.id
        ORDER BY f.id, wp.confidence DESC
    """)).fetchall()

print(f"    {len(waste_suppliers)} atık kaydı bulundu")

# ============================================================================
# 2. HAMMADDESİ İHTİYAÇ DUYANLARI AL (rawmaterial_needs'ten)
# ============================================================================
print("[2] Hammadde İhtiyaç Duyanlar Taranıyor...")
with engine.connect() as conn:
    material_buyers = conn.execute(text("""
        SELECT DISTINCT
            f.id as buyer_id,
            f.facility_name,
            f.city,
            rn.waste_code,
            rn.material_name,
            rn.annual_need_ton,
            rn.priority,
            rn.explanation
        FROM facility_rawmaterial_needs rn
        JOIN facilities f ON rn.facility_id = f.id
        ORDER BY f.id, rn.priority
    """)).fetchall()

print(f"    {len(material_buyers)} hammadde talep kaydı bulundu")

# ============================================================================
# 3. KOORDİNATLARI ÖNCEDENDEfl AL (batching)
# ============================================================================
print("[3] Facility Koordinatları Alınıyor...")
with engine.connect() as conn:
    coords = conn.execute(text("""
        SELECT id, latitude, longitude FROM facilities
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """)).fetchall()
    coord_dict = {c[0]: (c[1], c[2]) for c in coords}

print(f"    {len(coord_dict)} facility koordinatı bulundu")

# ============================================================================
# 4. ATIK KOD BAZINDA EŞLEŞTİR (optimize)
# ============================================================================
print("[4] Eşleştirmeler Hesaplanıyor...")

matches = []
total_potential_ton = 0

# Haversine mesafe hesaplama fonksiyonu
from math import radians, cos, sin, asin, sqrt

def haversine_distance(lat1, lon1, lat2, lon2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return round(c * 6371, 1)  # 6371 km = Earth radius

# Her atık kaydı için
for i, waste in enumerate(waste_suppliers):
    if (i + 1) % 500 == 0:
        print(f"    {i+1}/{len(waste_suppliers)} processed...")
    
    supplier_id, supplier_name, supplier_city, waste_code, waste_name, available_ton, confidence, waste_exp = waste
    
    # Her hammadde kaydı için
    for material in material_buyers:
        buyer_id, buyer_name, buyer_city, req_waste_code, material_name, need_ton, priority, material_exp = material
        
        # Aynı EWC koduna eşleşen mi?
        if waste_code == req_waste_code and supplier_id != buyer_id and available_ton > 0 and need_ton > 0:
            # Mesafe hesapla
            distance_km = None
            if supplier_id in coord_dict and buyer_id in coord_dict:
                lat1, lon1 = coord_dict[supplier_id]
                lat2, lon2 = coord_dict[buyer_id]
                if all([lat1, lon1, lat2, lon2]):
                    distance_km = haversine_distance(lat1, lon1, lat2, lon2)
            
            # Eşleştirme kalitesi (0-100)
            quality = min(100, int(confidence * 100 * (min(available_ton, need_ton) / max(available_ton, need_ton))))
            
            # Miktarı eşleşir mi?
            quantity_match = "✓ YETERLİ" if available_ton >= need_ton else "⚠ KISMEN"
            
            match = {
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "supplier_city": supplier_city,
                "buyer_id": buyer_id,
                "buyer_name": buyer_name,
                "buyer_city": buyer_city,
                "waste_code": waste_code,
                "waste_name": waste_name,
                "available_ton": available_ton,
                "needed_ton": need_ton,
                "quantity_match": quantity_match,
                "distance_km": distance_km,
                "quality": quality,
                "priority": priority
            }
            
            matches.append(match)
            total_potential_ton += min(available_ton, need_ton)

# Kalitesine göre sırala
matches_sorted = sorted(matches, key=lambda x: x['quality'], reverse=True)

print(f"    {len(matches_sorted)} olası eşleştirme bulundu")
print(f"    Toplam taşınabilir atık: {total_potential_ton:,.0f} ton\n")

# ============================================================================
# 4. EN İYİ EŞLEŞTİRMELERİ GÖSTER
# ============================================================================
print("="*80)
print("EN İYİ CIRCULAR ECONOMY EŞLEŞTİRMELERİ (Top 20)")
print("="*80)

for i, match in enumerate(matches_sorted[:20], 1):
    print(f"\n[{i}] {match['waste_code']} - {match['waste_name'][:40]}")
    print(f"    Verici: {match['supplier_name'][:45]} ({match['supplier_city']})")
    print(f"    Alıcı:  {match['buyer_name'][:45]} ({match['buyer_city']})")
    print(f"    Miktarlar: {match['available_ton']} ton (var) → {match['needed_ton']} ton (lazım) {match['quantity_match']}")
    if match['distance_km']:
        print(f"    Mesafe: {match['distance_km']} km")
    print(f"    Kalite Skoru: {match['quality']}/100 | Öncelik: {match['priority']}")

# ============================================================================
# 5. İSTATİSTİKLER
# ============================================================================
print("\n" + "="*80)
print("İSTATİSTİKLER")
print("="*80)

with engine.connect() as conn:
    # Eşleştirme kapsama
    result = conn.execute(text("""
        SELECT COUNT(DISTINCT facility_id) FROM facility_waste_predictions
    """))
    suppliers_with_waste = result.scalar()
    
    result = conn.execute(text("""
        SELECT COUNT(DISTINCT facility_id) FROM facility_rawmaterial_needs
    """))
    buyers_with_needs = result.scalar()

print(f"\nAtık Yönetimi Kapsama:")
print(f"  • Atık üreten/kaydı olan facility: {suppliers_with_waste}")
print(f"  • Hammadde ihtiyaç duyan facility: {buyers_with_needs}")
print(f"  • Olası eşleştirmeler: {len(matches_sorted)}")
print(f"  • Taşınabilir toplam atık: {total_potential_ton:,.0f} ton")

# Kalite dağılımı
quality_groups = {
    "Çok İyi (90+)": sum(1 for m in matches_sorted if m['quality'] >= 90),
    "İyi (70-89)": sum(1 for m in matches_sorted if 70 <= m['quality'] < 90),
    "Orta (50-69)": sum(1 for m in matches_sorted if 50 <= m['quality'] < 70),
    "Düşük (<50)": sum(1 for m in matches_sorted if m['quality'] < 50),
}

print(f"\nKalite Dağılımı:")
for group, count in quality_groups.items():
    pct = (count / len(matches_sorted) * 100) if matches_sorted else 0
    print(f"  • {group}: {count} ({pct:.1f}%)")

# Mesafe dağılımı
distances = [m['distance_km'] for m in matches_sorted if m['distance_km']]
if distances:
    print(f"\nMesafe Dağılımı:")
    print(f"  • Ortalama: {sum(distances)/len(distances):.0f} km")
    print(f"  • Min: {min(distances):.0f} km")
    print(f"  • Max: {max(distances):.0f} km")
    print(f"  • 50 km içi: {sum(1 for d in distances if d <= 50)}")

# ============================================================================
# 6. SONUÇLARI SAKLA
# ============================================================================
output_file = 'circular_economy_matches.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump({
        'timestamp': datetime.now().isoformat(),
        'total_matches': len(matches_sorted),
        'total_transferable_ton': total_potential_ton,
        'matches': [
            {
                'supplier': match['supplier_name'],
                'buyer': match['buyer_name'],
                'waste_code': match['waste_code'],
                'waste_name': match['waste_name'],
                'available': match['available_ton'],
                'needed': match['needed_ton'],
                'distance_km': match['distance_km'],
                'quality_score': match['quality']
            }
            for match in matches_sorted
        ]
    }, f, indent=2, ensure_ascii=False)

print(f"\n✓ Sonuçlar '{output_file}' dosyasına kaydedildi")

print("\n" + "="*80)
print(f"[{datetime.now().strftime('%H:%M:%S')}] Tamamlandı!")
print("="*80 + "\n")

engine.dispose()
