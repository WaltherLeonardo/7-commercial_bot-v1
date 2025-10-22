# scrapers/base.py
import os
import asyncio
from pathlib import Path
from typing import Optional, Callable
from playwright.async_api import async_playwright, BrowserContext, Page, Download

DEBUG_URL = os.getenv("DEBUG_URL", "http://localhost:9222")
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./data/downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

class BrowserSession:
    def __init__(self):
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        self.pw = await async_playwright().start()
        # ✅ Connect to your already open Chrome
        self.browser = await self.pw.chromium.connect_over_cdp(DEBUG_URL)
        self.context = self.browser.contexts[0]  # use the first Chrome profile context
        self.page = self.context.pages[0]        # use the first open tab
        await self.page.bring_to_front()
        print("✅ Connected to your existing Chrome session.")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # Don’t close the browser — you’re still using it manually
        await self.pw.stop()


async def click_and_download(page: Page, click_action: Callable[[], None], timeout_ms: int = 30000) -> Path:
    """Click something that triggers a file download and return saved file path."""
    async with page.expect_download(timeout=timeout_ms) as dl_info:
        await click_action()
    download: Download = await dl_info.value
    suggested = download.suggested_filename
    target = DOWNLOAD_DIR / suggested
    await download.save_as(target.as_posix())
    return target

async def goto_and_wait_ready(page: Page, url: str, selector_to_wait: str, timeout_ms: int = 30000):
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_selector(selector_to_wait, timeout=timeout_ms)