# scrapers/base.py
import os
from pathlib import Path
from typing import Optional, Iterable
from playwright.async_api import async_playwright, BrowserContext, Page

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
    
    async def list_pages(self) -> None:
        """Print index, title, and URL of all open tabs (for quick debugging)."""
        pages: Iterable[Page] = self.context.pages
        print("\n[TABS]")
        for i, p in enumerate(pages):
            try:
                title = await p.title()
                url = p.url
                print(f"  #{i:02d} | {title} | {url}")
            except Exception as e:
                print(f"  #{i:02d} | <unavailable> ({e})")
        print("[/TABS]\n")

    async def _match_page(
        self,
        *,
        title_contains: Optional[str] = None,
        url_contains: Optional[str] = None,
        index: Optional[int] = None,
    ) -> Page:
        """
        Find a page by partial title, partial URL, or index.
        - title_contains/url_contains are case-insensitive substrings
        - index selects by order in context.pages
        Raises ValueError if not found.
        """
        pages = self.context.pages

        if index is not None:
            try:
                return pages[index]
            except IndexError:
                raise ValueError(f"No page at index {index}. Total open tabs: {len(pages)}")

        def _contains(haystack: str, needle: str) -> bool:
            return needle.lower() in haystack.lower()

        for p in pages:
            t = await p.title()
            u = p.url
            ok_title = _contains(t, title_contains) if title_contains else False
            ok_url = _contains(u, url_contains) if url_contains else False
            if (title_contains and ok_title) or (url_contains and ok_url):
                return p

        crit = f"title~'{title_contains}'" if title_contains else f"url~'{url_contains}'"
        raise ValueError(f"No tab matched {crit}. Use list_pages() to see open tabs.")

    async def select_page(
        self,
        *,
        title_contains: Optional[str] = None,
        url_contains: Optional[str] = None,
        index: Optional[int] = None,
        bring_to_front: bool = True,
    ) -> Page:
        """
        Set self.page to the tab that matches the criteria and optionally bring it to front.
        Returns the selected Page.
        """
        p = await self._match_page(title_contains=title_contains, url_contains=url_contains, index=index)
        if bring_to_front:
            await p.bring_to_front()
        self.page = p
        return p
    


async def click_and_download(page: Page, button, timeout_ms: int = 60000) -> Path:
    """Click a button (Locator or callable) that triggers a download and return the saved path."""
    # Normalize: allow passing a Locator OR a callable that performs the click
    async def _do_click():
        if callable(button):
            await button()
        else:
            # it's a Locator
            await button.wait_for(state="visible", timeout=timeout_ms)
            await button.scroll_into_view_if_needed()
            await button.click()

    async with page.expect_download(timeout=timeout_ms) as dl_info:
        await _do_click()

    download = await dl_info.value
    target = DOWNLOAD_DIR / download.suggested_filename
    await download.save_as(target.as_posix())
    return target

async def goto_and_wait_ready(page: Page, url: str, selector_to_wait: str, timeout_ms: int = 30000):
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_selector(selector_to_wait, timeout=timeout_ms)