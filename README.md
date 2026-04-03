# Hackaton AI 2026

FastAPI service for the archive assistant prototype.

Implemented endpoints:
- `POST /ai/get_info`
- `POST /ai/save_doc`
- `POST /ai/chat`

Core capabilities:
- document classification and structured extraction
- document indexing with chunk embeddings
- archive search with `persons_shadow` and hybrid retrieval

Local run:

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Tests:

```bash
.venv/bin/pytest -q
```
