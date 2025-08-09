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