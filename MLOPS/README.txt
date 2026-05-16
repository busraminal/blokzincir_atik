ATIK — MLOps (hızlı stack)
==========================

Tek komut (Docker Desktop açık olmalı):

  PowerShell:  .\MLOPS\up.ps1
  veya:        cd MLOPS  →  docker compose up --build -d

İsteğe bağlı — Ollama konteyner içinde:

  cd MLOPS
  docker compose --profile ollama up --build -d

Çalışan servisler:
  • atik-api    → http://127.0.0.1:8000/docs
  • postgres    → localhost:5432  postgres / admin  / postgre_database

İlk kurulumda `init-db.sql` otomatik çalışır (örnek tesisler, waste_types, match_candidates).
Yeniden seed için:  docker compose down -v  sonra tekrar up

API özeti (Swagger’da tam liste):
  • GET  /api/v1/predict/ewc-by-nace?nace=24.10
  • GET  /api/v1/predict/health-llm
  • POST /api/v1/llm/chat   (OpenAI uyumlu gövde)
  • POST /api/v1/llm/waste-advice?nace_code=38.12
  • GET  /api/v1/facilities/1/matches

LLM:
  • Windows: bilgisayarda Ollama (11434) + Docker API → OLLAMA_BASE_URL=http://host.docker.internal:11434 (compose’da varsayılan)
  • Bulut: atik-api ortamına OPENAI_API_KEY

Durdur:

  cd MLOPS  →  docker compose down
  veya:  .\MLOPS\down.ps1

Node zinciri: proje kökünde .\start-atik-dev.ps1 (Docker’da 8000 API varsa yerel uvicorn atlanır).

Dosyalar:
  docker-compose.yml   Postgres + API (+ isteğe ollama profili)
  Dockerfile.api
  requirements-docker.txt
  init-db.sql
  up.ps1 / down.ps1 / up.bat
