# Hackaton AI 2026

FastAPI service for the archive assistant prototype.

Implemented endpoints:
- `POST /ai/get_info`
- `POST /ai/save_doc`
- `POST /ai/chat`
- `POST /ai/extract_pdf_text`
- `POST /ai/fact_of_day`
- `POST /ai/voice`
- `POST /ai/asr`

Core capabilities:
- document classification and structured extraction
- document indexing with chunk embeddings
- archive search with `persons_shadow` and hybrid retrieval
- PDF OCR fallback
- daily archive fact generation
- TTS and ASR

Docker run:

```bash
docker compose up --build -d
```

Service URLs:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/health
```

Useful Docker commands:

```bash
docker compose logs -f app
docker compose down
```

Notes:

- Docker Desktop must be running
- if you use WSL, Docker Desktop WSL integration for this distro must be enabled
- `docker-compose.yml` reads secrets from `.env`
- SQLite data is persisted through `./data:/app/data`
- inside the container the app always listens on `0.0.0.0:8000`

Local run without Docker:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Tests:

```bash
.venv/bin/pytest -q
```

PDF extraction:

- if `LAYOUT_PARSING_BASE_URL` is set, `POST /ai/extract_pdf_text` first calls `<base_url>/layout-parsing`
- if that upstream returns an error or an unreadable response, the service falls back to the current OpenAI PDF OCR flow
- if `LAYOUT_PARSING_BASE_URL` is empty, the service uses OpenAI PDF OCR directly
