# Shared bits for Playwright-backed spiders: request helper and small utils.
import os
import json
import scrapy
from urllib.parse import urljoin

EXTRA_HEADERS = json.loads(os.environ.get("SCRAPY_EXTRA_HEADERS", "{}"))
EXTRA_COOKIES = json.loads(os.environ.get("SCRAPY_EXTRA_COOKIES", "{}"))
HTTP_PROXY = os.environ.get("SCRAPY_HTTP_PROXY")

class BaseProductSpider(scrapy.Spider):
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "AUTOTHROTTLE_ENABLED": True,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 2,
        "DOWNLOAD_DELAY": 0.25,
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy_playwright.middleware.ScrapyPlaywrightDownloadHandler": 543,
            "scrapy_user_agents.middlewares.RandomUserAgentMiddleware": 400,
        },
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 20000,
    }

    def playwright_request(self, url: str, **kwargs):
        headers = {**EXTRA_HEADERS}
        cookies = [{"name": k, "value": v} for k, v in EXTRA_COOKIES.items()]
        meta = {
            "playwright": True,
            "playwright_context": f"ctx-{self.name}",
            "playwright_context_kwargs": {
                "user_agent": headers.get("User-Agent"),
                "java_script_enabled": True,
                "ignore_https_errors": True,
                "record_video_dir": None,
                "viewport": {"width": 1366, "height": 768},
            },
            "playwright_page_methods": [("wait_for_load_state", {"state": "networkidle"})],
        }
        if cookies:
            meta["playwright_context_kwargs"]["storage_state"] = {"cookies": cookies}
        if HTTP_PROXY:
            meta["proxy"] = HTTP_PROXY
        return scrapy.Request(url, headers=headers or None, meta=meta, **kwargs)

    def abs(self, response, sel):
        src = response.css(sel).get()
        return urljoin(response.url, src) if src else ""