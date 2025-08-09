import scrapy
from urllib.parse import urlencode
from .base_spider import BaseProductSpider

class UniqloSpider(BaseProductSpider):
    name = "uniqlo"
    allowed_domains = ["www.uniqlo.com", "uniqlo.com"]

    def __init__(self, query: str = "shirt", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        q = urlencode({"q": query})
        self.start_urls = [f"https://www.uniqlo.com/us/en/search/?{q}"]

    def start_requests(self):
        for url in self.start_urls:
            yield self.playwright_request(url, callback=self.parse)

    def parse(self, response):
        # Uniqlo search -> PDP.
        for href in response.css("a[href*='/product/']::attr(href)").getall()[:80]:
            yield self.playwright_request(response.urljoin(href), callback=self.parse_product)

    def parse_product(self, response):
        def text(css):
            v = response.css(css).xpath("string(.)").get()
            return (v or "").strip()
        yield {
            "id": response.url,
            "title": text("h1, [data-test='product-name']"),
            "price": text("[data-test='product-price'], .price, [itemprop='price']") or 0,
            "currency": "USD",
            "brand": "UNIQLO",
            "sizes": [],
            "colors": [],
            "image_url": self.abs(response, "img::attr(src)"),
            "product_url": response.url,
            "availability": text("[data-test='availability']") or "In Stock",
            "description": text("[data-test='description'], .product-description"),
            "category": "Fashion",
            "rating": 0,
            "reviews": 0,
            "retailer": "UNIQLO",
            "search_query": self.query,
        }
