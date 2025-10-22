# scrapers/classic_cotizador.py
import os
import pandas as pd
from pathlib import Path
from playwright.async_api import Page
from .base import BrowserSession, goto_and_wait_ready, click_and_download
from sqlalchemy import create_engine
from db import DB_URL

CLASSIC_URL = os.getenv("CLASSIC_URL")

async def run_classic_export() -> Path:
    async with BrowserSession() as b:
        page: Page = b.page
        await goto_and_wait_ready(page, CLASSIC_URL, selector_to_wait='text="COTIZADOR VEHICULAR - SAN ISIDRO"')
        await page.get_by_text("wrojas@panaautos.com.pe").click()
        print("😎😎 logging out")

        await page.wait_for_selector('button:has-text("Ingresar")')
        await page.get_by_text("Ingresar").click(force=True)        
        print("😎😎 ask to log in")

        await page.wait_for_selector('[data-test-id="wrojas@panaautos.com.pe"]')
        await page.get_by_text("wrojas@panaautos.com.pe").click()
        print("😎😎 logging in")
        
        # await page.wait_for_selector('text="Escribir contraseña"')
        await page.wait_for_selector('input#i0118', state='visible')
        await page.fill('input#i0118', 'CafeCaliente2626')
        print("😎😎 password set")

        await page.wait_for_selector('input#idSIButton9', state='visible')
        await page.click('input#idSIButton9')
        print("😎😎 enter")

        print("😎😎")
        

        # Navigate to the report section and click the Excel export
        await page.click('text="Reporte"')
        await page.wait_for_selector('button:has-text("Excel")')

        xlsx_path = await click_and_download(
            page,
            click_action=lambda: page.click('button:has-text("Excel")')
        )
        return xlsx_path

def upsert_classic_to_sqlite(xlsx_path: Path):
    df = pd.read_excel(xlsx_path)
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        df.to_sql("classic_cotizaciones", conn, if_exists="append", index=False)

async def run():
    xlsx = await run_classic_export()
    upsert_classic_to_sqlite(xlsx)
