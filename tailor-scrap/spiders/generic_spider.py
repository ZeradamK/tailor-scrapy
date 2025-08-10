import json
from urllib.parse import urlencode
from .base_spider import BaseProductSpider

# Config-backed spider: use per-domain CSS selectors from retailers/config.json.
with open("retailers/config.json", "r") as f:
    RETAILERS = json.load(f)

class GenericRetailerSpider(BaseProductSpider):
    name = "generic"

    def __init__(self, domain: str, query: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        self.query = query
        self.cfg = RETAILERS[domain]
        self.start_urls = [self.cfg["search"].format(query=query)]
        self.brand = self.cfg.get("brand", domain)

    def start_requests(self):
        for url in self.start_urls:
            yield self.playwright_request(url, callback=self.parse)

    def parse(self, response):
        # Search result page -> product detail pages (best-effort selectors).
        links = response.css(self.cfg["itemLink"]).getall()[:100]
        for href in links:
            yield self.playwright_request(response.urljoin(href), callback=self.parse_product)

    def parse_product(self, response):
        def text(sel):
            v = response.css(self.cfg[sel]).xpath("string(.)").get() if self.cfg.get(sel) else None
            return (v or "").strip()
        yield {
            "id": response.url,
            "title": text("title"),
            "price": text("price") or 0,
            "currency": "USD",
            "brand": self.brand,
            "sizes": [],
            "colors": [],
            "image_url": self.abs(response, self.cfg["image"]) if self.cfg.get("image") else "",
            "product_url": response.url,
            "availability": text("availability") or "",
            "description": text("description") or "",
            "category": "Fashion",
            "rating": 0,
            "reviews": 0,
            "retailer": self.brand,
            "search_query": self.query,
        }