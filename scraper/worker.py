# Worker process: pops jobs, runs spiders, streams items, and updates cache/metrics.
# Keep side effects scoped; the API stays stateless.
import os
import json
import time
import subprocess
import redis
import hashlib

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PROXY_POOL = [p.strip() for p in os.getenv("PROXY_POOL", "").split(",") if p.strip()]
CACHE_TTL = int(os.getenv("CACHE_TTL", "1800"))
PER_DOMAIN_DELAY = float(os.getenv("PER_DOMAIN_DELAY", "0.2"))
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Specific spiders for sites we care about deeply.
RETAILER_TO_SPIDER = {
    "H&M": "spiders/hm_spider.py",
    "Zara": "spiders/zara_spider.py",
    "NIKE": "spiders/nike_spider.py",
    "UNIQLO": "spiders/uniqlo_spider.py",
}
# Generic spider covers many domains via config.
GENERIC_SPIDER = "spiders/generic_spider.py"


def pick_proxy(proxy_url: str | None, affinity_key: str | None) -> str | None:
    # Respect explicit proxy first; otherwise pick a sticky entry from the pool.
    if proxy_url:
        return proxy_url
    if not PROXY_POOL:
        return None
    key = affinity_key or "default"
    idx = int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(PROXY_POOL)
    return PROXY_POOL[idx]


def cache_key(retailer: str, query: str) -> str:
    # Stable key for (retailer, query) cache entries.
    return f"cache:{retailer}:{hashlib.sha256(query.encode()).hexdigest()}"


while True:
    job_raw = r.lpop("scrape:queue")
    if not job_raw:
        time.sleep(0.2)
        continue

    payload = json.loads(job_raw)
    job_id = payload["job_id"]
    query = payload["query"]
    retailer = payload["retailer"]
    use_cache = payload.get("use_cache", True)
    proxy_url = pick_proxy(payload.get("proxy_url"), payload.get("ip_affinity_key"))
    headers = payload.get("headers") or {}
    cookies = payload.get("cookies") or {}

    stream_key = f"scrape:stream:{job_id}"

    # Cache hit path: stream from Redis and exit early.
    ck = cache_key(retailer, query)
    if use_cache:
        cached = r.get(ck)
        if cached:
            try:
                items = json.loads(cached)
                for it in items:
                    r.publish(stream_key, json.dumps({"type": "item", "item": it}))
                r.publish(stream_key, json.dumps({"type": "complete", "code": 0}))
                r.hset(f"scrape:job:{job_id}", mapping={"state": "finished", "cached": "1"})
                r.incrby("metrics:items_total", len(items))
                continue
            except Exception:
                pass

    # Light per-domain throttle; avoid hammering the same host.
    last_key = f"ratelimit:last:{retailer}"
    last = r.get(last_key)
    if last:
        elapsed = time.time() - float(last)
        if elapsed < PER_DOMAIN_DELAY:
            time.sleep(PER_DOMAIN_DELAY - elapsed)
    r.set(last_key, time.time())

    # Route: label -> specific spider; domain -> generic spider.
    if "." in retailer:
        spider_file = GENERIC_SPIDER
        extra_args = ["-a", f"domain={retailer}"]
    else:
        spider_file = RETAILER_TO_SPIDER.get(retailer) or RETAILER_TO_SPIDER.get(retailer.upper())
        extra_args = []

    r.hset(f"scrape:job:{job_id}", mapping={"state": "running", "spider": spider_file or "unknown"})

    if not spider_file:
        r.hset(f"scrape:job:{job_id}", "state", "error")
        r.publish(stream_key, json.dumps({"type": "error", "error": "unsupported retailer"}))
        continue

    # Pass per-job session hints via env.
    env = os.environ.copy()
    if proxy_url:
        env["SCRAPY_HTTP_PROXY"] = proxy_url
    if headers:
        env["SCRAPY_EXTRA_HEADERS"] = json.dumps(headers)
    if cookies:
        env["SCRAPY_EXTRA_COOKIES"] = json.dumps(cookies)

    items_collected: list[dict] = []

    try:
        # Stream jsonlines to stdout; worker forwards each line over pub/sub.
        cmd = [
            "scrapy", "runspider", spider_file,
            "-a", f"query={query}",
            *extra_args,
            "-s", "FEED_URI=-",
            "-s", "FEED_FORMAT=jsonlines",
            "-s", "FEED_EXPORT_ENCODING=utf-8",
            "-s", "ROBOTSTXT_OBEY=False",
            "-s", "AUTOTHROTTLE_ENABLED=True",
            "-s", "DOWNLOAD_DELAY=0.5",
        ]
        if proxy_url:
            cmd += ["-s", "HTTPPROXY_ENABLED=True", "-s", f"HTTP_PROXY={proxy_url}"]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=os.path.dirname(__file__))
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            try:
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict):
                    items_collected.append(obj)
                    r.publish(stream_key, json.dumps({"type": "item", "item": obj}))
                else:
                    r.publish(stream_key, json.dumps({"type": "log", "log": line[:500]}))
            except Exception:
                r.publish(stream_key, json.dumps({"type": "log", "log": line[:500]}))
        code = proc.wait(timeout=5)
        if use_cache and items_collected:
            r.setex(ck, CACHE_TTL, json.dumps(items_collected))
        r.hset(f"scrape:job:{job_id}", "state", "finished")
        r.incrby("metrics:items_total", len(items_collected))
        r.publish(stream_key, json.dumps({"type": "complete", "code": code}))
    except Exception as e:
        r.hset(f"scrape:job:{job_id}", "state", "error")
        r.publish(stream_key, json.dumps({"type": "error", "error": str(e)}))
