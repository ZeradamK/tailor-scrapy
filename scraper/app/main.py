# API layer: accepts scrape jobs and streams results over SSE.
# Keep this process stateless; Redis holds job state and pub/sub.
import os
import json
import uuid
from typing import Dict, Any, Optional, Dict as TDict
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title="Fashion Scraper Service")

class ScrapeRequest(BaseModel):
    # Per-job knobs so callers can bring their own session/proxy.
    query: str
    retailer: str
    proxy_url: Optional[str] = None
    headers: Optional[TDict[str, str]] = None
    cookies: Optional[TDict[str, str]] = None
    ip_affinity_key: Optional[str] = None
    use_cache: bool = True

@app.post("/scrape")
def scrape(req: ScrapeRequest) -> Dict[str, Any]:
    # Push a job and return a handle immediately.
    job_id = str(uuid.uuid4())
    payload = {
        "job_id": job_id,
        "query": req.query,
        "retailer": req.retailer,
        "proxy_url": req.proxy_url,
        "headers": req.headers or {},
        "cookies": req.cookies or {},
        "ip_affinity_key": req.ip_affinity_key,
        "use_cache": req.use_cache,
    }
    r.rpush("scrape:queue", json.dumps(payload))
    r.hset(f"scrape:job:{job_id}", mapping={
        "state": "queued",
        "retailer": req.retailer,
        "query": req.query,
        "proxy": req.proxy_url or "",
    })
    r.incr("metrics:jobs_total")
    r.incr(f"metrics:jobs:{req.retailer}")
    return {"job_id": job_id}

@app.get("/status/{job_id}")
def status(job_id: str) -> Dict[str, Any]:
    # Quick readback for UIs or diagnostics.
    data = r.hgetall(f"scrape:job:{job_id}")
    if not data:
        raise HTTPException(404, "job not found")
    return data

@app.get("/events/{job_id}")
def events(job_id: str):
    # Fan out items/logs via Redis pub/sub. Clients consume as SSE.
    stream_key = f"scrape:stream:{job_id}"

    def event_stream():
        pubsub = r.pubsub()
        pubsub.subscribe(stream_key)
        try:
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                yield f"data: {message['data']}\n\n"
        finally:
            pubsub.unsubscribe(stream_key)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/metrics")
def metrics() -> Dict[str, Any]:
    # Minimal counters; good enough for a quick health glance.
    return {
        "jobs_total": int(r.get("metrics:jobs_total") or 0),
        "items_total": int(r.get("metrics:items_total") or 0),
    }