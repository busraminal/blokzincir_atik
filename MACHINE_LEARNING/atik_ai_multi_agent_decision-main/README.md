# ATIK AI - Multi-Agent Circular Economy Decision System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17+-blue?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)

**🌍 AI-Powered Industrial Waste-to-Material Matching Platform**

*Türkiye Enerji Verimlilik Merkezi*

[Hızlı Başlangıç](#-hızlı-başlangıç) •
[API Dokümantasyonu](#-api-endpoints) •
[Multi-Agent Sistem](#-multi-agent-sistem) •
[Katkıda Bulunma](#-katkıda-bulunma)

</div>

---

## 📋 Proje Hakkında

**ATIK AI**, endüstriyel tesisler arasında atık ve hammadde ihtiyaçlarını yapay zeka ile eşleştiren, döngüsel ekonomi prensipleri temelinde çalışan bir **kapalı döngü endüstriyel ekosistem** platformudur.

### 🎯 Temel Özellikler

| Özellik | Değer | Açıklama |
|---------|-------|----------|
| **Eşleştirme Kapasitesi** | 541,332+ | Potansiyel atık-hammadde eşleştirmesi |
| **Yıllık Transfer** | 5.3M ton | Transfer edilebilir atık kapasitesi |
| **Firma Sayısı** | 303 | Eşleştirilmiş firma (Ankara bölgesi) |
| **LLM Modeli** | GPT-5-mini | Azure OpenAI entegrasyonu |
| **Ortalama Mesafe** | 1 km | Coğrafi eşleştirme (Haversine) |

### 🏗️ Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                        ATIK AI Platform                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Extraction │  │  Matching   │  │ Feasibility │  Multi-Agent │
│  │    Agent    │──│    Agent    │──│    Agent    │  Orchestrator│
│  └─────────────┘  └─────────────┘  └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    FastAPI REST API                         ││
│  │  /facilities  /matching  /feasibility  /distance  /health  ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐│
│  │PostgreSQL │  │  W2RKG    │  │  Distance │  │    SWAN       ││
│  │ Database  │  │ Knowledge │  │Calculator │  │  Economics    ││
│  └───────────┘  └───────────┘  └───────────┘  └───────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Hızlı Başlangıç

### Gereksinimler

- Python 3.12+
- PostgreSQL 17+
- Azure OpenAI API erişimi (opsiyonel)

### Kurulum

```bash
# 1. Repository'yi klonla
git clone https://github.com/your-org/atik_ai_multi_agent_decision.git
cd atik_ai_multi_agent_decision

# 2. Virtual environment oluştur
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. Bağımlılıkları yükle
pip install -r requirements.txt

# 4. Environment değişkenlerini ayarla
cp .env.example .env
# .env dosyasını düzenle
```

### Veritabanı Yapılandırması

```env
# .env dosyası
DATABASE_URL=postgresql://postgres:admin@localhost:5432/postgre_database
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
```

### API'yi Başlat

```bash
# Development modu
uvicorn atik_ai.api.routes:app --reload --host 0.0.0.0 --port 8000

# Swagger UI
# http://localhost:8000/docs
```

---

## 📦 Proje Yapısı

```
atik_ai_multi_agent_decision/
├── atik_ai/                          # Ana Python paketi
│   ├── agents/                       # Multi-agent sistemi
│   │   ├── agents.py                 # Agent factory fonksiyonları
│   │   ├── team.py                   # Agno orchestrator
│   │   ├── base.py                   # Base agent sınıfları
│   │   └── tools.py                  # Agent araçları
│   ├── api/                          # FastAPI REST API
│   │   ├── routes.py                 # API endpoint tanımları
│   │   └── schemas.py                # Pydantic request/response modelleri
│   ├── core/                         # Temel modüller
│   │   ├── database.py               # PostgreSQL bağlantı yönetimi
│   │   ├── models.py                 # SQLAlchemy ORM modelleri
│   │   ├── config.py                 # Konfigürasyon yönetimi
│   │   └── exceptions.py             # Custom exception sınıfları
│   ├── distance/                     # Mesafe hesaplama modülleri
│   │   ├── calculator.py             # Haversine & API hesaplama
│   │   ├── cache.py                  # Mesafe cache (Redis)
│   │   └── matrix.py                 # Distance matrix işlemleri
│   ├── economics/                    # Ekonomik analiz modülleri
│   │   ├── feasibility.py            # SWAN fizibilite analizi
│   │   ├── logistics.py              # Lojistik maliyet hesaplama
│   │   ├── pricing.py                # Dinamik fiyatlandırma
│   │   ├── pricing_table.py          # EWC bazlı fiyat tablosu
│   │   └── optimizer.py              # Ekonomik optimizasyon
│   ├── knowledge/                    # W2RKG bilgi grafiği
│   │   ├── graph.py                  # Graf yapısı
│   │   ├── academic.py               # Akademik veri entegrasyonu
│   │   ├── extractor.py              # Bilgi çıkarma
│   │   └── fusion.py                 # Veri füzyonu
│   ├── matching/                     # Eşleştirme motoru
│   │   ├── engine.py                 # Ana matching algoritması
│   │   ├── technical.py              # Teknik uyumluluk analizi
│   │   └── temporal.py               # Zamansal eşleştirme
│   └── prediction/                   # LLM tahmin modülleri
│       ├── predictor.py              # Tahmin motoru
│       ├── encoders.py               # Text encoding (BERT/GPT)
│       ├── embeddings.py             # Embedding modelleri
│       └── training.py               # Model fine-tuning
├── scripts/                          # Standalone scriptler
│   ├── circular_economy_matching.py  # Ana eşleştirme scripti
│   ├── waste_predictor_llm.py        # Atık tahmin motoru
│   └── rawmaterial_predictor_llm.py  # Hammadde ihtiyaç tahmini
├── examples/                         # Örnek kullanımlar
├── data/                             # Veri dosyaları (gitignore)
├── requirements.txt                  # Python bağımlılıkları
├── requirements-minimal.txt          # Minimal production bağımlılıklar
├── .env.example                      # Environment şablonu
└── README.md                         # Bu dosya
```

---

## 🔌 API Endpoints

### Base URL: `http://localhost:8000/api/v1`

### Facilities (Tesisler)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/facilities/` | Tüm tesisleri listele |
| `GET` | `/facilities/{id}` | Tesis detayı |
| `POST` | `/facilities/` | Yeni tesis ekle |
| `GET` | `/facilities/{id}/matches` | Tesis eşleşmeleri |

### Matching (Eşleştirme)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `POST` | `/matching/search` | Atık koduna göre eşleştirme ara |
| `GET` | `/matching/waste-types` | Atık tiplerini listele |
| `GET` | `/matching/ewc-codes` | EWC kodlarını listele |

### Feasibility (Fizibilite)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `POST` | `/feasibility/analyze` | SWAN fizibilite analizi |

### Distance (Mesafe)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `POST` | `/distance/calculate` | İki tesis arası mesafe |

### Health (Sistem Durumu)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/health/` | Sistem sağlık kontrolü |
| `GET` | `/health/stats` | Veritabanı istatistikleri |

---

## 📊 API Kullanım Örnekleri

### Fizibilite Analizi

```bash
curl -X POST "http://localhost:8000/api/v1/feasibility/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "source_facility_id": 4,
    "receiver_facility_id": 11,
    "ewc_code": "70213",
    "waste_quantity_ton": 50,
    "distance_km": 25
  }'
```

**Response:**
```json
{
  "source_facility_id": 4,
  "receiver_facility_id": 11,
  "is_feasible": true,
  "source_profit": 12450.50,
  "receiver_profit": 8320.75,
  "transport_cost": {
    "total": 2850.00,
    "fuel": 1200.00,
    "driver": 450.00,
    "maintenance": 200.00,
    "loading": 1000.00
  },
  "break_even": {
    "min_price": 45.50,
    "max_price": 125.00,
    "recommended": 85.25
  },
  "decision": "PROCEED",
  "confidence": 0.92
}
```

### Tesis Listesi

```bash
curl "http://localhost:8000/api/v1/facilities/?page=1&per_page=10&city=ANKARA"
```

### JavaScript (Fetch)

```javascript
const analyzeWasteExchange = async (data) => {
  const response = await fetch('http://localhost:8000/api/v1/feasibility/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_facility_id: data.sourceId,
      receiver_facility_id: data.receiverId,
      ewc_code: data.wasteCode,
      waste_quantity_ton: data.quantity,
      distance_km: data.distance
    })
  });
  return response.json();
};
```

---

## 🤖 Multi-Agent Sistem

### Agent Türleri

| Agent | Görev | Araçlar |
|-------|-------|---------|
| **Extraction Agent** | Atık/hammadde verisi çıkarma | LLM, NER, Text Parser |
| **Matching Agent** | Eşleştirme ve ranking | W2RKG, Embedding Search |
| **Feasibility Agent** | Ekonomik fizibilite | SWAN Model, Cost Calculator |
| **Coordinator** | Orkestrasyon | All agents |

### Kullanım

```python
from atik_ai.agents import create_atik_team

# Team oluştur
team = create_atik_team()

# Sorgu gönder
result = team.orchestrate(
    query="150106 kodlu karışık ambalajları alabilen firmayı bul",
    context={"limit": 10, "max_distance_km": 50}
)

print(result.matches)
print(result.feasibility_analysis)
```

---

## 🗄️ Veritabanı Şeması

### Ana Tablolar

| Tablo | Kayıt Sayısı | Açıklama |
|-------|--------------|----------|
| `facilities` | 303 | Endüstriyel tesisler |
| `facility_waste_predictions` | 4,613 | LLM-tahmin edilen atık türleri |
| `facility_rawmaterial_needs` | 3,034 | LLM-tahmin edilen hammadde ihtiyaçları |
| `waste_types` | 46 | EWC atık kategorileri |
| `sectors` | 41 | NACE endüstri sektörleri |
| `w2rkg_library` | 33,679 | Akademik Waste→Process→Resource üçlemeleri |

---

## ⚙️ Konfigürasyon

### Environment Değişkenleri

```env
# Database
DATABASE_URL=postgresql://postgres:admin@localhost:5432/postgre_database
DB_ECHO=false

# Azure OpenAI
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini

# Redis (opsiyonel)
REDIS_URL=redis://localhost:6379/0

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Geocoding
ARCGIS_API_KEY=your_key
```

---

## 🐳 Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "atik_ai.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Çalıştırma

```bash
# Build
docker build -t atik-ai:latest .

# Run
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e AZURE_OPENAI_API_KEY=... \
  atik-ai:latest
```

---

## 📈 Performans Metrikleri

| İşlem | Süre | Notlar |
|-------|------|--------|
| Atık tahminleme (303 firma) | ~2-3 min | 10 parallel workers |
| Hammadde tahminleme (303 firma) | ~2-3 min | 10 parallel workers |
| Geocoding (303 adres) | ~5 min | ArcGIS API |
| Circular economy matching | ~12 sec | 4.6K×3K matrix |
| API startup | ~2 sec | FastAPI + SQLAlchemy |
| Single feasibility analysis | ~50 ms | SWAN model |

---

## 🧪 Test

```bash
# Unit testleri çalıştır
pytest tests/ -v

# Coverage ile
pytest tests/ --cov=atik_ai --cov-report=html

# Belirli modül testi
pytest tests/test_feasibility.py -v
```

---

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'i push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın

---

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

---

## 📞 İletişim

- **Proje**: ATIK AI Multi-Agent Decision System
- **Organizasyon**: RDC AI Team
- **Finansman**: Türkiye Enerji Verimlilik Merkezi

---

<div align="center">

**Son Güncelleme**: 31 Mart 2026 | **Versiyon**: 1.0.0

Made with ❤️ by RDC AI Team

</div>
