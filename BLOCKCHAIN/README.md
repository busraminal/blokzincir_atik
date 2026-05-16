# ATIK — Blockchain (DLT + Hyperledger Fabric)

## İki çalışma modu

### A) Demo zincir (dosya tabanlı) — en hızlı

1. `BLOCKCHAIN\atik-dlt` klasöründe `.env` oluşturun (`\.env.example` şablonu).
2. `npm install` → `npm start`
3. Tarayıcı: `http://127.0.0.1:<PORT>/blokzincir.html?server=1` (PORT genelde 5055)

Veriler `chain.json` benzeri dosyada tutulur; Fabric gerekmez.

### B) Tam Fabric ağı (üretim benzeri)

1. **Docker Desktop** + **WSL2 (Ubuntu)** açık olsun.
2. Proje yolu **Türkçe karakter içermemesi** önerilir (WSL `wslpath` / script sorunları için). Gerekirse `C:\dev\atik-work\` altına kopyalayın.
3. PowerShell (yönetici gerekmez), **atik-dlt** kökünden:

```powershell
cd "C:\...\atık\BLOCKCHAIN\atik-dlt"
.\scripts\Calistir-TamStack.ps1
```

Script sırası: `scripts\bootstrap-fabric.sh` (WSL) → ardından `npm run start:fabric` (Windows Node, `USE_FABRIC=1`).

4. Sorun giderme: `KURULUM.txt`, `TAM-KURULUM.txt`, `FABRIC-Gercek-Sistem.txt`, `BLOCKCHAIN_DEMO_KANIT.md` dosyalarına bakın (yollar `BLOCKCHAIN\atik-dlt\` altına göre güncellendi).

## Klasör yapısı

- `BLOCKCHAIN/atik-dlt/` — Node sunucusu, `lib/fabricClient.js`, `chaincode/`
- `WEB/` — statik arayüz (sunucu `WEB_STATIC` ile buradan sunulur)
- `MLOPS/` — Docker ile Postgres + FastAPI

## API + zincir birlikte

- Yerel: proje kökünde `.\start-atik-dev.ps1` (Ollama + Node; Docker’da API varsa 8000 için uvicorn atlanır).
- `atik-dlt\.env` içinde `ATIK_AI_PROXY_URL=http://127.0.0.1:8000` → ML API proxy.
