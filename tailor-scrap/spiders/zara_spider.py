import scrapy
from urllib.parse import urlencode
from .base_spider import BaseProductSpider

class ZaraSpider(BaseProductSpider):
    name = "zara"
    allowed_domains = ["www.zara.com", "zara.com"]

    def __init__(self, query: str = "shirt", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        q = urlencode({"searchTerm": query})
        self.start_urls = [f"https://www.zara.com/us/en/search?{q}"]

    def start_requests(self):
        for url in self.start_urls:
            yield self.playwright_request(url, callback=self.parse)

    def parse(self, response):
        # Collect product links from search; cap to keep latency in check.
        for href in response.css("a[href*='/p']::attr(href), a[href*='/product/']::attr(href)").getall()[:80]:
            yield self.playwright_request(response.urljoin(href), callback=self.parse_product)

    def parse_product(self, response):
        def text(css):
            v = response.css(css).xpath("string(.)").get()
            return (v or "").strip()
        yield {
            "id": response.url,
            "title": text("h1, [itemprop='name']"),
            "price": text("[itemprop='price'], [data-qa-action='product-card-price']") or 0,
            "currency": "USD",
            "brand": "Zara",
            "sizes": [],
            "colors": [],
            "image_url": self.abs(response, "img::attr(src)"),
            "product_url": response.url,
            "availability": text(".availability") or "In Stock",
            "description": text(".product-description, [data-qa-action='description']"),
            "category": "Fashion",
            "rating": 0,
            "reviews": 0,
            "retailer": "Zara",
            "search_query": self.query,
        }
