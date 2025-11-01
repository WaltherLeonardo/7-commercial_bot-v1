# scrapers/classic_cotizador.py
import os
import pandas as pd
from pathlib import Path
from playwright.async_api import Page
from .base import BrowserSession, goto_and_wait_ready, click_and_download
from sqlalchemy import create_engine
from db import DB_URL
from datetime import datetime, timedelta, timezone
from hashlib import sha1
from urllib.parse import urljoin

FAST_URL = os.getenv("FAST_URL")
day = str(datetime.now().day)  # used to click the day in the calendar

def _fmt_input_date(d):       # -> "MM/DD/YYYY"
    return f"{d.month:02d}/{d.day:02d}/{d.year}"

async def _open_range_datepicker(page):
    # Open the "Rango de fechas" input
    dp_input = page.locator('p-datepicker input[placeholder*="Rango de fechas"]')
    await dp_input.click()
    panel = page.get_by_role("dialog", name="Choose Date").last
    await panel.wait_for(state="visible")
    await page.wait_for_timeout(50)
    return panel

async def _click_day_by_date(panel, d):
    # PrimeNG uses 0-based months in data-date (0..11)
    zero_based = f'{d.year}-{d.month-1}-{d.day}'
    one_based  = f'{d.year}-{d.month}-{d.day}'  # fallback, just in case

    loc = panel.locator(f'span.p-datepicker-day[data-date="{zero_based}"]')
    if await loc.count() == 0:
        loc = panel.locator(f'span.p-datepicker-day[data-date="{one_based}"]')
    await loc.first.wait_for(state="visible")
    await loc.first.click()

async def _table_fingerprint(page, rows_to_check=8):
    """
    Build a small fingerprint from the first N rows using DOCUMENTO (col 2) and CLIENTE (col 5).
    Adjust nth-child indexes if your table changes.
    """
    documentos = page.locator("table.p-datatable-table tbody tr td:nth-child(2)")
    clientes   = page.locator("table.p-datatable-table tbody tr td:nth-child(5)")

    n = min(rows_to_check, await documentos.count(), await clientes.count())
    parts = []
    for i in range(n):
        doc = (await documentos.nth(i).text_content() or "").strip()
        cli = (await clientes.nth(i).text_content() or "").strip()
        parts.append(f"{i}:{doc}|{cli}")
    return sha1("\n".join(parts).encode("utf-8")).hexdigest()


async def wait_table_refreshed(page, start_date, end_date, timeout=20000):
    """
    Confirms:
      1) date range input shows the selected range, and
      2) DOCUMENTO/CLIENTE fingerprint of the first rows has changed.
    """
    # 1) Ensure datepicker dialog is gone
    dlg = page.get_by_role("dialog", name="Choose Date").last
    try:
        await dlg.wait_for(state="hidden", timeout=3000)
    except:
        pass

    # 2) Wait until range input reflects selection
    expected = f"{_fmt_input_date(start_date)} - {_fmt_input_date(end_date)}"
    dp_input = page.locator('p-datepicker input[placeholder*="Rango de fechas"]')
    for _ in range(int(timeout/250)):
        val = await dp_input.input_value()
        if expected in val:
            break
        await page.wait_for_timeout(250)
    else:
        raise TimeoutError(f"Date range input did not update to '{expected}'")

    # 3) If overlay exists, use it as a quick path
    overlay = page.locator(".p-datatable-loading-overlay, .p-datatable-loading-icon")
    try:
        await overlay.wait_for(state="visible", timeout=1500)
        await overlay.wait_for(state="hidden", timeout=timeout)
        return
    except:
        pass

    # 4) Fingerprint change on DOCUMENTO/CLIENTE
    rows = page.locator("table.p-datatable-table tbody tr")
    await rows.first.wait_for(timeout=timeout)  # ensure at least 1 row

    baseline = await _table_fingerprint(page)
    for _ in range(int(timeout/300)):
        cur = await _table_fingerprint(page)
        if cur != baseline:
            # print("✅ Table fingerprint changed.")
            return
        await page.wait_for_timeout(300)

    raise TimeoutError("Table content (DOCUMENTO/CLIENTE) did not change after range selection.")

async def select_date_range_today_to_tomorrow(page):
    tz = timezone(timedelta(hours=-5))  # Lima
    today = datetime.now(tz).date()
    tomorrow = today + timedelta(days=1)

    panel = await _open_range_datepicker(page)

    # start: today
    await _click_day_by_date(panel, today)

    # if tomorrow is next month, go next once
    if (tomorrow.year, tomorrow.month) != (today.year, today.month):
        await panel.locator("button.p-datepicker-next").click()
        await page.wait_for_timeout(50)

    # end: tomorrow
    await _click_day_by_date(panel, tomorrow)

    # allow table to reload after second click
    await wait_table_refreshed(page, start_date=today, end_date=tomorrow)


async def run_fast_export() -> Path:
    async with BrowserSession() as b:
        await b.list_pages()  # 👀to see the pages
        await b.select_page(title_contains="Cotizador Vehicular")
        page: Page = b.page
        # home page
        await goto_and_wait_ready(page, FAST_URL, selector_to_wait='text="RECEPCIÓN DE CLIENTE"')
        print("😎😎 we are in!")

        # Navigate to "Ver Cotizaciones" page
        await page.get_by_role("link", name="Ver Cotizaciones").click()
        await page.wait_for_url("**/historialcotizacion*")
        
        #history_url = urljoin(FAST_URL, "/panel/cotizacion/historialcotizacion")
        #await page.goto(history_url)
        #await page.wait_for_url("**/historialcotizacion*")
        print("😎😎 inside in report page!")

        await select_date_range_today_to_tomorrow(page)


        print("🦗🦗")

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