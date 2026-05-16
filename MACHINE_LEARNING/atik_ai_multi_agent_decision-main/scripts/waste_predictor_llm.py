"""
ATIK AI - LLM Tabanlı Atık Tahmini
Faaliyet metninden hangi atıkların üretilebileceğini tahmin eder.
"""
import os
import json
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from openai import AzureOpenAI

load_dotenv()

# Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

# Veritabanı bağlantısı
engine = create_engine('postgresql://postgres:admin@localhost:5432/postgre_database')


def get_waste_codes_from_db() -> str:
    """Veritabanındaki tüm atık türlerini çek"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT waste_code, description 
            FROM waste_types 
            ORDER BY waste_code
        """))
        
        waste_list = []
        for row in result:
            waste_list.append(f"{row[0]} - {row[1]}")
        
        return "\n".join(waste_list)


# Veritabanından atık kodlarını çek
WASTE_CODES = get_waste_codes_from_db()
print(f"✅ Veritabanından {len(WASTE_CODES.split(chr(10)))} atık türü yüklendi")


def predict_waste_for_activity(activity_text: str, firma_name: str = "") -> Dict:
    """
    Faaliyet metninden potansiyel atık türlerini tahmin et.
    
    Args:
        activity_text: Firma faaliyet açıklaması
        firma_name: Firma adı (opsiyonel)
    
    Returns:
        Tahmin sonuçları
    """
    
    prompt = f"""Aşağıdaki firma faaliyet açıklamasına göre, bu firmanın üretebileceği endüstriyel atıkları belirle.

**Firma:** {firma_name}
**Faaliyet:** {activity_text}

**VERİTABANINDAKİ ATIK TÜRLERİ (SADECE BUNLARDAN SEÇ):**
{WASTE_CODES}

**Görev:**
1. SADECE yukarıdaki listeden bu faaliyetle ilgili atıkları seç
2. Her atık için tahmini yıllık miktar (ton)
3. Güven skoru (0-1 arası)

**SADECE JSON formatında yanıt ver:**
{{
    "firma": "{firma_name}",
    "atiklar": [
        {{
            "ewc_kod": "120109",
            "atik_adi": "Halojen içermeyen işleme emülsiyonları",
            "tahmini_miktar_ton": 50,
            "guven_skoru": 0.85,
            "aciklama": "Talaşlı imalattan kaynaklanan soğutma sıvıları"
        }}
    ],
    "sektor_tahmini": "Metal İşleme",
    "nace_kod_tahmini": "25.62"
}}
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_GENERATIVE_MODEL_DEPLOYMENT_NAME", "gpt-5-mini"),
            messages=[
                {"role": "system", "content": "Sen bir endüstriyel atık yönetimi uzmanısın. EWC kodlarını ve NACE sınıflandırmasını çok iyi biliyorsun."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        return {"error": str(e), "firma": firma_name}


def save_predictions_to_db(predictions: List[Dict]):
    """
    Tahminleri veritabanına kaydet.
    
    Args:
        predictions: Tahmin sonuçları listesi
    """
    with engine.connect() as conn:
        # Tabloyu oluştur (yoksa)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS facility_waste_predictions (
                id SERIAL PRIMARY KEY,
                facility_id INTEGER REFERENCES facilities(id),
                waste_code VARCHAR(10),
                waste_name TEXT,
                estimated_ton FLOAT,
                confidence FLOAT,
                explanation TEXT,
                predicted_sector TEXT,
                predicted_nace VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        
        # Eski tahminleri sil (varsa)
        facility_ids = [p.get('facility_id') for p in predictions if p.get('facility_id')]
        if facility_ids:
            conn.execute(text("""
                DELETE FROM facility_waste_predictions 
                WHERE facility_id = ANY(:ids)
            """), {"ids": facility_ids})
            conn.commit()
        
        # Yeni tahminleri ekle
        insert_count = 0
        for pred in predictions:
            if "error" in pred:
                continue
                
            facility_id = pred.get('facility_id')
            sector = pred.get('sektor_tahmini', '')
            nace = pred.get('nace_kod_tahmini', '')
            
            for atik in pred.get('atiklar', []):
                conn.execute(text("""
                    INSERT INTO facility_waste_predictions 
                    (facility_id, waste_code, waste_name, estimated_ton, confidence, explanation, predicted_sector, predicted_nace)
                    VALUES (:fac_id, :code, :name, :ton, :conf, :exp, :sector, :nace)
                """), {
                    "fac_id": facility_id,
                    "code": atik.get('ewc_kod', ''),
                    "name": atik.get('atik_adi', ''),
                    "ton": atik.get('tahmini_miktar_ton', 0),
                    "conf": atik.get('guven_skoru', 0),
                    "exp": atik.get('aciklama', ''),
                    "sector": sector,
                    "nace": nace
                })
                insert_count += 1
        
        conn.commit()
        print(f"\n💾 Veritabanına {insert_count} atık tahmini kaydedildi")


def process_single_facility(facility):
    """Tek bir tesis için tahmin yap (thread-safe)"""
    fac_id, name, activity = facility
    prediction = predict_waste_for_activity(activity, name)
    prediction['facility_id'] = fac_id
    return fac_id, name, prediction


def process_all_facilities(limit: int = 10, max_workers: int = 5):
    """
    Veritabanındaki tüm tesisler için paralel atık tahmini yap.
    
    Args:
        limit: İşlenecek maksimum tesis sayısı
        max_workers: Paralel thread sayısı
    """
    
    with engine.connect() as conn:
        # Tesisleri al
        result = conn.execute(text("""
            SELECT id, facility_name, activity_text 
            FROM facilities 
            WHERE activity_text IS NOT NULL 
            LIMIT :limit
        """), {"limit": limit})
        
        facilities = result.fetchall()
        
    total = len(facilities)
    print(f"\n{'='*60}")
    print(f"   {total} TESİS İÇİN ATIK TAHMİNİ YAPILIYOR ({max_workers} thread)")
    print(f"{'='*60}\n")
    
    all_predictions = []
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Tüm işleri gönder
        future_to_facility = {
            executor.submit(process_single_facility, fac): fac 
            for fac in facilities
        }
        
        # Sonuçları al
        for future in as_completed(future_to_facility):
            completed += 1
            try:
                fac_id, name, prediction = future.result()
                
                if "error" not in prediction:
                    atik_count = len(prediction.get('atiklar', []))
                    print(f"[{completed}/{total}] ✅ {name[:40]}... → {atik_count} atık")
                else:
                    print(f"[{completed}/{total}] ❌ {name[:40]}... → Hata")
                
                all_predictions.append(prediction)
                
            except Exception as e:
                print(f"[{completed}/{total}] ❌ Hata: {e}")
    
    # JSON'a kaydet
    with open('predictions_output.json', 'w', encoding='utf-8') as f:
        json.dump(all_predictions, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Sonuçlar 'predictions_output.json' dosyasına kaydedildi")
    
    # Veritabanına kaydet
    save_predictions_to_db(all_predictions)
    
    return all_predictions


def demo_single_prediction():
    """Tek bir firma için demo tahmin"""
    
    # Örnek firma
    activity = "Alüminyum bar, çubuk, tel ve profil, tüp, boru ve bağlantı parçaları imalatı (alaşımdan olanlar dahil)"
    firma = "AKTAŞ MEKANİK ALÜMİNYUM"
    
    print(f"\n{'='*60}")
    print("   DEMO TAHMİN")
    print(f"{'='*60}")
    print(f"\nFirma: {firma}")
    print(f"Faaliyet: {activity}")
    print("\nTahmin yapılıyor...")
    
    result = predict_waste_for_activity(activity, firma)
    
    print(f"\n{'='*60}")
    print("   SONUÇ")
    print(f"{'='*60}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        workers = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        process_all_facilities(limit, workers)
    else:
        demo_single_prediction()
