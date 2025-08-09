import scrapy
from urllib.parse import urlencode
from .base_spider import BaseProductSpider

class NikeSpider(BaseProductSpider):
    name = "nike"
    allowed_domains = ["www.nike.com", "nike.com"]

    def __init__(self, query: str = "shoes", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        self.start_urls = [f"https://www.nike.com/w?q={query}"]

    def start_requests(self):
        for url in self.start_urls:
            yield self.playwright_request(url, callback=self.parse)

    def parse(self, response):
        # Nike PDPs live under /t/. Grab a reasonable slice to keep latency down.
        for href in response.css("a[href*='/t/']::attr(href)").getall()[:80]:
            yield self.playwright_request(response.urljoin(href), callback=self.parse_product)

    def parse_product(self, response):
        def text(css):
            v = response.css(css).xpath("string(.)").get()
            return (v or "").strip()
        yield {
            "id": response.url,
            "title": text("h1, [data-test='product-title']"),
            "price": text("[data-test='product-price'], .price, [itemprop='price']") or 0,
            "currency": "USD",
            "brand": "Nike",
            "sizes": [],
            "colors": [],
            "image_url": self.abs(response, "img::attr(src)"),
            "product_url": response.url,
            "availability": text("[data-test='product-availability']") or "In Stock",
            "description": text("[data-test='product-description'], .description"),
            "category": "Fashion",
            "rating": 0,
            "reviews": 0,
            "retailer": "Nike",
            "search_query": self.query,
        }
