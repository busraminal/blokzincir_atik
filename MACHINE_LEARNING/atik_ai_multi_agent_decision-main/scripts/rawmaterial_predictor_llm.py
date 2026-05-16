"""
ATIK AI - LLM Tabanlı Ham Madde Tahmini
Faaliyet metninden hangi ham maddelerin kullanıldığını tahmin eder.
Bu sayede: Firma A'nın atığı = Firma B'nin ham maddesi → Eşleşme!
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
    """Veritabanındaki tüm atık türlerini çek (ham madde olarak kullanılabilecekler)"""
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
print(f"✅ Veritabanından {len(WASTE_CODES.split(chr(10)))} atık/materyal türü yüklendi")


def predict_rawmaterials_for_activity(activity_text: str, firma_name: str = "") -> Dict:
    """
    Faaliyet metninden ihtiyaç duyulan ham maddeleri tahmin et.

    Args:
        activity_text: Firma faaliyet açıklaması
        firma_name: Firma adı (opsiyonel)

    Returns:
        Tahmin sonuçları (ham madde ihtiyaçları EWC kodlarıyla)
    """

    prompt = f"""Aşağıdaki firma faaliyet açıklamasına göre, bu firmanın üretim sürecinde kullandığı ham maddeleri ve girdileri belirle.

**Firma:** {firma_name}
**Faaliyet:** {activity_text}

**MEVCUT MATERYAL LİSTESİ (SADECE BUNLARDAN SEÇ):**
{WASTE_CODES}

**Görev:**
Bu firma hangi materyallere ihtiyaç duyar? Özellikle yukarıdaki listede yer alan ve başka firmaların atığı olabilecek materyalleri bul.

Örnek düşünce:
- Alüminyum profil imalatı → alüminyum hurda/talaş ihtiyacı var (başka bir metalin atığı)
- Plastik ürünleri geri dönüşüm → çeşitli plastik atıklar gerekli
- Organik gübre üretimi → gıda atıkları, biyolojik atıklar gerekli

**SADECE JSON formatında yanıt ver:**
{{
    "firma": "{firma_name}",
    "ham_maddeler": [
        {{
            "ewc_kod": "120101",
            "materyal_adi": "Demir ve çelik talaşı",
            "yillik_ihtiyac_ton": 200,
            "oncelik": "yüksek",
            "aciklama": "Alüminyum eritme için sekonder hammadde olarak kullanılır",
            "alternatif_kaynaklar": ["metal işleme atıkları", "hurda"]
        }}
    ],
    "sektor_tahmini": "Metal İşleme",
    "nace_kod_tahmini": "24.42",
    "geri_donusum_kapasitesi": "var"
}}

Not: Sadece yukarıdaki listede yer alan materyalleri seç. Listede olmayan ham maddeler için boş liste döndür.
"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_GENERATIVE_MODEL_DEPLOYMENT_NAME", "gpt-5-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sen bir endüstriyel ekoloji ve döngüsel ekonomi uzmanısın. "
                        "Firmaların üretim süreçlerinde hangi ikincil hammaddeleri ve atıkları "
                        "girdi olarak kullanabileceğini çok iyi biliyorsun. "
                        "EWC kodlarını ve NACE sınıflandırmasını tam olarak biliyorsun."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return result

    except Exception as e:
        return {"error": str(e), "firma": firma_name}


def save_rawmaterials_to_db(predictions: List[Dict]):
    """
    Ham madde tahminlerini veritabanına kaydet.
    Atık-hammadde eşleştirmesi için facility_rawmaterial_needs tablosuna yazar.
    """
    with engine.connect() as conn:
        # Tabloyu oluştur (yoksa)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS facility_rawmaterial_needs (
                id SERIAL PRIMARY KEY,
                facility_id INTEGER REFERENCES facilities(id),
                waste_code VARCHAR(10),
                material_name TEXT,
                annual_need_ton FLOAT,
                priority VARCHAR(20),
                explanation TEXT,
                predicted_sector VARCHAR(200),
                predicted_nace VARCHAR(10),
                recycling_capacity TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

        # Eski kayıtları sil (varsa)
        facility_ids = [p.get('facility_id') for p in predictions if p.get('facility_id')]
        if facility_ids:
            conn.execute(text("""
                DELETE FROM facility_rawmaterial_needs
                WHERE facility_id = ANY(:ids)
            """), {"ids": facility_ids})
            conn.commit()

        # Yeni kayıtları ekle
        insert_count = 0
        for pred in predictions:
            if "error" in pred:
                continue

            facility_id = pred.get('facility_id')
            sector = pred.get('sektor_tahmini', '')
            nace = pred.get('nace_kod_tahmini', '')
            recycling = pred.get('geri_donusum_kapasitesi', '')

            for mat in pred.get('ham_maddeler', []):
                conn.execute(text("""
                    INSERT INTO facility_rawmaterial_needs
                    (facility_id, waste_code, material_name, annual_need_ton,
                     priority, explanation, predicted_sector, predicted_nace, recycling_capacity)
                    VALUES (:fac_id, :code, :name, :ton, :priority, :exp, :sector, :nace, :recycling)
                """), {
                    "fac_id": facility_id,
                    "code": mat.get('ewc_kod', ''),
                    "name": mat.get('materyal_adi', ''),
                    "ton": mat.get('yillik_ihtiyac_ton', 0),
                    "priority": mat.get('oncelik', ''),
                    "exp": mat.get('aciklama', ''),
                    "sector": sector,
                    "nace": nace,
                    "recycling": recycling
                })
                insert_count += 1

        conn.commit()
        print(f"\n💾 Veritabanına {insert_count} ham madde ihtiyacı kaydedildi")


def process_single_facility(facility):
    """Tek bir tesis için tahmin yap (thread-safe)"""
    fac_id, name, activity = facility
    prediction = predict_rawmaterials_for_activity(activity, name)
    prediction['facility_id'] = fac_id
    return fac_id, name, prediction


def process_all_facilities(limit: int = 10, max_workers: int = 5):
    """
    Veritabanındaki tüm tesisler için paralel ham madde tahmini yap.

    Args:
        limit: İşlenecek maksimum tesis sayısı
        max_workers: Paralel thread sayısı
    """

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, facility_name, activity_text
            FROM facilities
            WHERE activity_text IS NOT NULL
            LIMIT :limit
        """), {"limit": limit})
        facilities = result.fetchall()

    total = len(facilities)
    print(f"\n{'='*60}")
    print(f"   {total} TESİS İÇİN HAM MADDE TAHMİNİ YAPILIYOR ({max_workers} thread)")
    print(f"{'='*60}\n")

    all_predictions = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_facility = {
            executor.submit(process_single_facility, fac): fac
            for fac in facilities
        }

        for future in as_completed(future_to_facility):
            completed += 1
            try:
                fac_id, name, prediction = future.result()

                if "error" not in prediction:
                    mat_count = len(prediction.get('ham_maddeler', []))
                    print(f"[{completed}/{total}] ✅ {name[:40]}... → {mat_count} ham madde")
                else:
                    print(f"[{completed}/{total}] ❌ {name[:40]}... → Hata")

                all_predictions.append(prediction)

            except Exception as e:
                print(f"[{completed}/{total}] ❌ Hata: {e}")

    # JSON'a kaydet
    with open('rawmaterials_output.json', 'w', encoding='utf-8') as f:
        json.dump(all_predictions, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Sonuçlar 'rawmaterials_output.json' dosyasına kaydedildi")

    # Veritabanına kaydet
    save_rawmaterials_to_db(all_predictions)

    return all_predictions


def demo_single_prediction():
    """Tek bir firma için demo tahmin"""

    activity = "Alüminyum bar, çubuk, tel ve profil, tüp, boru ve bağlantı parçaları imalatı (alaşımdan olanlar dahil)"
    firma = "AKTAŞ MEKANİK ALÜMİNYUM"

    print(f"\n{'='*60}")
    print("   DEMO HAM MADDE TAHMİNİ")
    print(f"{'='*60}")
    print(f"\nFirma: {firma}")
    print(f"Faaliyet: {activity}")
    print("\nTahmin yapılıyor...")

    result = predict_rawmaterials_for_activity(activity, firma)

    print(f"\n{'='*60}")
    print("   SONUÇ")
    print(f"{'='*60}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def show_circular_matches():
    """
    Atık-Hammadde eşleşmelerini göster:
    Firma A'nın atığı = Firma B'nin ham maddesi
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                f_producer.facility_name AS atik_ureticisi,
                wp.waste_code,
                wp.waste_name AS atik_adi,
                wp.estimated_ton AS uretilen_ton,
                f_consumer.facility_name AS hammadde_kullanicisi,
                rn.material_name AS hammadde_adi,
                rn.annual_need_ton AS ihtiyac_ton,
                rn.priority AS oncelik
            FROM facility_waste_predictions wp
            JOIN facilities f_producer ON wp.facility_id = f_producer.id
            JOIN facility_rawmaterial_needs rn ON wp.waste_code = rn.waste_code
            JOIN facilities f_consumer ON rn.facility_id = f_consumer.id
            WHERE wp.facility_id != rn.facility_id
              AND wp.confidence >= 0.6
              AND rn.priority IN ('yüksek', 'orta')
            ORDER BY rn.priority, wp.estimated_ton DESC
            LIMIT 20
        """))

        matches = result.fetchall()

    if not matches:
        print("\n⚠️ Henüz eşleşme yok. Önce her iki tahmin scriptini çalıştırın.")
        return

    print(f"\n{'='*70}")
    print("   DÖNGÜSEL EKONOMİ EŞLEŞMELERİ (Atık → Ham Madde)")
    print(f"{'='*70}\n")

    for m in matches:
        print(f"♻️  {m[0][:35]}")
        print(f"    Atık: {m[2]} ({m[3]} ton) [{m[1]}]")
        print(f"    → {m[4][:35]}")
        print(f"    Ham Madde: {m[5]} (İhtiyaç: {m[6]} ton) [{m[7]}]")
        print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            workers = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            process_all_facilities(limit, workers)
        elif sys.argv[1] == "--matches":
            show_circular_matches()
    else:
        demo_single_prediction()
