# scrapers/classic_cotizador.py
import os
import pandas as pd
from pathlib import Path
from playwright.async_api import Page
from .base import BrowserSession, goto_and_wait_ready, click_and_download
from sqlalchemy import create_engine
from db import DB_URL
from datetime import datetime


CLASSIC_URL = os.getenv("CLASSIC_URL")
day = str(datetime.now().day)  # used to click the day in the calendar

async def run_classic_export() -> Path:
    async with BrowserSession() as b:
        page: Page = b.page
        # home page
        await goto_and_wait_ready(page, CLASSIC_URL, selector_to_wait='text="COTIZADOR VEHICULAR - SAN ISIDRO"')
        print("😎😎 we are in!")
        
        # steps into reports page
        card = page.locator("div.card-option", has_text="GESTION REPORTES")
        await card.get_by_role("button", name="MOSTRAR").click()
        print("😎😎 into reports")

        # steps into commercial reports page
        await page.get_by_role("tab", name="Comercial").click()
        print("😎😎 into commercai reports")

        # steps to open filters
        await page.locator('a.p-accordion-header-link', has_text="COTIZACIONES").wait_for(state="visible")
        await page.locator('a.p-accordion-header-link', has_text="COTIZACIONES").click()        
        
        # Fecha Inicio = today
        await page.locator('input[placeholder="Fecha de Inicio"] + button').click()
        await page.locator(f'.p-datepicker:visible .p-datepicker-calendar td:has(span:has-text("{day}"))').click()

        # Fecha Fin = today
        await page.locator('input[placeholder="Fecha de Fin"] + button').click()
        await page.locator(f'.p-datepicker:visible .p-datepicker-calendar td:has(span:has-text("{day}"))').click()

        # Sociedad = "PANA AUTOS S.A."
        sociedad_trigger = page.locator('label:has-text("Sociedad")').locator('xpath=../../..').locator('.p-dropdown-trigger')
        await sociedad_trigger.click()
        await page.get_by_role("option", name="PANA AUTOS S.A.").click()

        # Open "Tipo Quote" dropdown
        tipo_trigger = page.locator('label:has-text("Tipo")').locator('xpath=../../..').locator('.p-multiselect-trigger')
        await tipo_trigger.click()
        # Select RETAIL (scoped to the open panel)
        panel = page.locator('.p-multiselect-panel:visible')
        await panel.locator('li[aria-label="RETAIL"]').click()
        # (optional) close the panel
        await page.keyboard.press("Escape")
        print("😎😎 ready to download")
        
        btn = page.get_by_role("button", name="Descargar Reporte de Cotizaciones")

        xlsx_path = await click_and_download(page, btn)
        print(f"😎😎 we get the path {xlsx_path}")
        return xlsx_path
                    
def upsert_classic_to_sqlite(csv_path: Path):
    # Read the downloaded CSV instead of XLSX
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig")

    # Create SQLAlchemy connection
    engine = create_engine(DB_URL, future=True)
    with engine.begin() as conn:
        # Append new rows to 'classic_cotizaciones' table
        df.to_sql("classic_cotizaciones", conn, if_exists="append", index=False)

async def run():
    xlsx = await run_classic_export()
    upsert_classic_to_sqlite(xlsx)
