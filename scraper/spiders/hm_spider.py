import scrapy
from urllib.parse import urlencode
from .base_spider import BaseProductSpider

class HmSpider(BaseProductSpider):
    name = "hm"
    allowed_domains = ["www2.hm.com", "hm.com"]

    def __init__(self, query: str = "shirt", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        q = urlencode({"q": query})
        self.start_urls = [f"https://www2.hm.com/en_us/search-results.html?{q}"]

    def start_requests(self):
        for url in self.start_urls:
            yield self.playwright_request(url, callback=self.parse)

    def parse(self, response):
        # H&M search grid -> product pages.
        for href in response.css(".product-item a::attr(href)").getall()[:80]:
            yield self.playwright_request(response.urljoin(href), callback=self.parse_product)

    def parse_product(self, response):
        def text(css):
            v = response.css(css).xpath("string(.)").get()
            return (v or "").strip()
        yield {
            "id": response.url,
            "title": text("h1, .product-name, [data-product-name]"),
            "price": text(".price, [data-price]") or 0,
            "currency": "USD",
            "brand": "H&M",
            "sizes": [],
            "colors": [],
            "image_url": self.abs(response, "img::attr(src)"),
            "product_url": response.url,
            "availability": text(".availability") or "In Stock",
            "description": text(".product-description, [data-product-description]"),
            "category": "Fashion",
            "rating": 0,
            "reviews": 0,
            "retailer": "H&M",
            "search_query": self.query,
        }
