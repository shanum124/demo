# Adaptive Learning Engine

A typed adaptive-learning service built with FastAPI, Pydantic v2, SQLite, Qdrant, Redis/Celery adapters, and Ollama. The Python service owns document intelligence; the Node service owns authentication, uploads, and application records.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn ai_services.main:app --reload --port 8001
```

The default development app uses local SQLite, local Qdrant, and an in-memory Redis substitute. Start Ollama separately when LLM report editing or mock generation is required. Mock generation fails explicitly when no configured model can return a validated, syllabus-scoped test; it does not substitute generic questions.

API documentation is available at `http://127.0.0.1:8001/docs`.

## Ingestion flow

`POST /ingest` accepts a syllabus plus zero or more `pyqs` and `notes` documents. It extracts text, creates source-derived syllabus nodes, parses PYQ metadata, chunks notes, indexes chunks with `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions), calculates deterministic coverage, persists the structured evidence, and returns an `AnalyzerInput` payload. The Node setup endpoint forwards each document type separately and then submits that payload to `/strategy/generate`.

The analyzer owns all numerical metrics. Its ROI formula is:

$$
ROI = \frac{weightage\_pct}{100} \times (1 + frequency) \times (1 + difficulty) \times (1 - coverage)
$$

`frequency` is the proportion of supplied source papers containing the node. Missing years, marks, and difficulties remain missing; they are not invented.

## Qdrant storage

The default is local Qdrant storage under `data/qdrant`. The configured embedding model and dimension are `ALE_EMBEDDING_MODEL` and `ALE_EMBEDDING_DIMENSION`; the defaults are `sentence-transformers/all-MiniLM-L6-v2` and `384`. Changing either requires a new collection and reindexing. To switch to Qdrant Cloud, set `ALE_QDRANT_URL`, `ALE_QDRANT_API_KEY`, and optionally `ALE_QDRANT_COLLECTION`; when `ALE_QDRANT_URL` is set, the local path is not opened.

## Tests

```powershell
pytest -q
```
