# scrapers/fast_cotizador.py
import os
import pandas as pd
from pathlib import Path
from playwright.async_api import Page
from .base import BrowserSession, goto_and_wait_ready, click_and_download
from sqlalchemy import create_engine
from db import DB_URL

FAST_URL = os.getenv("FAST_URL")

async def run_fast_export() -> Path:
    async with BrowserSession(headless=True) as b:
        page: Page = b.page

        # 1) Open and wait for something that proves the page is ready
        await goto_and_wait_ready(page, FAST_URL, selector_to_wait='button:has-text("Exportar")')

        # 2) (Optional) apply filters, login, etc. Example:
        # await page.fill('#username', os.getenv("FAST_USER"))
        # await page.fill('#password', os.getenv("FAST_PASS"))
        # await page.click('button:has-text("Ingresar")')
        # await page.wait_for_selector('#filters-ready')

        # 3) Trigger the export and capture the download
        xlsx_path = await click_and_download(
            page,
            click_action=lambda: page.click('button:has-text("Exportar")')
        )
        return xlsx_path

def upsert_fast_to_sqlite(xlsx_path: Path):
    df = pd.read_excel(xlsx_path)
    # optional: normalize columns here…
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        df.to_sql("fast_cotizaciones", conn, if_exists="append", index=False)

async def run():
    xlsx = await run_fast_export()
    upsert_fast_to_sqlite(xlsx)