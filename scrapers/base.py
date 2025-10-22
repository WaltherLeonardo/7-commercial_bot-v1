# scrapers/base.py
import os
import asyncio
from pathlib import Path
from typing import Callable, Optional
from playwright.async_api import async_playwright, BrowserContext, Page, Download

# Paths
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./data/downloads"))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

USER_DATA_DIR = Path(os.getenv("USER_DATA_DIR", "./data/user_profile"))
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

class BrowserSession:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.pw = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        # ✅ Start Playwright and use persistent context
        self.pw = await async_playwright().start()
        self.context = await self.pw.chromium.launch_persistent_context(
            USER_DATA_DIR.as_posix(),
            headless=self.headless,
            accept_downloads=True,
            args=["--no-sandbox"]
        )
        self.page = await self.context.new_page()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # ✅ Persistent context keeps cookies and localStorage
        if self.context:
            await self.context.close()
        if self.pw:
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