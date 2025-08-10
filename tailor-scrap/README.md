Tailor Scrap
============

Lightweight in-house scraper service (no external SERP/Firecrawl APIs).

Features
- Streams results via SSE
- Per-job headers/cookies/proxy pass-through
- IP affinity key for sticky proxy selection
- Mobile emulation knob via header `X-Viewport: mobile`

Run locally
1. Start Redis (optional if you already have one):
   - `docker run -p 6379:6379 redis:7-alpine`
2. Install Python deps in `tailor-scrap/`:
   - `pip install -r requirements.txt`
   - `python -m playwright install --with-deps chromium`
3. Run API:
   - `uvicorn app.main:app --host 0.0.0.0 --port 8001`
4. Run worker in another shell:
   - `python worker.py`

API
- POST `/scrape` { query, retailer, proxy_url?, headers?, cookies?, ip_affinity_key?, use_cache? }
- GET `/events/{job_id}` server-sent events stream {type: item|log|complete}
- GET `/status/{job_id}`
- GET `/metrics`

Notes
- To force mobile layout on JS-heavy PDPs, set header `X-Viewport: mobile`.
- To use caller IP, do not set `proxy_url` and deploy API behind a trusted proxy; forward `User-Agent`, `Accept-Language`, cookies from client to preserve session.
# Scraper Microservice

This service exposes a small FastAPI API to queue Scrapy jobs via Redis and stream results using Redis Pub/Sub.

## Requirements
- Python 3.11 (recommended via Miniconda on Windows)
- Redis (local `redis://localhost:6379` or configure `REDIS_URL`)

## Setup
```
conda create -n fashion-scraper python=3.11 -y
conda activate fashion-scraper
pip install -r requirements.txt
playwright install chromium
```

## Run
- Start Redis
- Start API:
```
uvicorn app.main:app --reload --port 8001
```
- Start worker:
```
python worker.py
```

## API
- POST /scrape { query, retailer } -> { job_id }
- GET /status/{job_id} -> job state
- GET /events/{job_id} -> SSE stream of items/logs/complete