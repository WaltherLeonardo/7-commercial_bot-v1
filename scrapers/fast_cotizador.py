# scrapers/classic_cotizador.py
import os
import pandas as pd
from pathlib import Path
from playwright.async_api import Page
from .base import BrowserSession, goto_and_wait_ready, click_and_download
from sqlalchemy import create_engine
from db import DB_URL
from datetime import datetime, timedelta, timezone
import re

FAST_URL = os.getenv("FAST_URL")
RANGE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}\s-\s\d{2}/\d{2}/\d{4}$")

async def _get_range_input(page):
    return page.locator('p-datepicker input[placeholder*="Rango de fechas"]').first

def _fmt_input_date(d):       # -> "MM/DD/YYYY"
    return f"{d.month:02d}/{d.day:02d}/{d.year}"

async def assert_range_selected(page, start_date, end_date, timeout=8000):
    """
    Confirms the date input shows exactly:
      MM/DD/YYYY - MM/DD/YYYY
    for the provided start_date and end_date.
    """
    expected = f"{_fmt_input_date(start_date)} - {_fmt_input_date(end_date)}"
    inp = await _get_range_input(page)

    end_ts = page.context._loop.time() + timeout / 1000
    while page.context._loop.time() < end_ts:
        try:
            val = await inp.input_value()
            if val and RANGE_RE.match(val) and val == expected:
                return
        except:
            pass
        await page.wait_for_timeout(150)

    raise RuntimeError(f"El rango de fechas no quedó aplicado. Esperado: '{expected}'.")

async def _open_range_datepicker(page):
    dp_input = await _get_range_input(page)
    await dp_input.click()
    panel = page.get_by_role("dialog", name="Choose Date").last
    await panel.wait_for(state="visible")
    await page.wait_for_timeout(50)
    return panel

async def _click_day_by_date(panel, d):
    # Your calendar uses 0-based month in data-date; keep a fallback
    zero_based = f'{d.year}-{d.month-1}-{d.day}'
    one_based  = f'{d.year}-{d.month}-{d.day}'
    loc = panel.locator(f'span.p-datepicker-day[data-date="{zero_based}"]')
    if await loc.count() == 0:
        loc = panel.locator(f'span.p-datepicker-day[data-date="{one_based}"]')
    await loc.first.wait_for(state="visible")
    await loc.first.click()

async def select_date_range_today_to_tomorrow(page):
    # Lima
    tz = timezone(timedelta(hours=-5))
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

    # ✅ guarantee the range really stuck
    await assert_range_selected(page, today, tomorrow)

async def download_with_range_guard(page, reselect=None, timeout=20000):
    """
    Clicks the download button and captures the file.
    - Validates that the range input contains 2 dates (MM/DD/YYYY - MM/DD/YYYY).
    - Supports different button variants.
    - Retries once if the site shows the 'No se ha seleccionado dos fechas' toast.
    :param reselect: optional async callable to re-select the range on retry
                     e.g., lambda: select_date_range_today_to_tomorrow(page)
    """
    async def _has_two_dates():
        val = await (await _get_range_input(page)).input_value()
        return bool(val and RANGE_RE.match(val)), val

    # --- 1) pre-click guard -------------------------------------------------
    ok, val = await _has_two_dates()
    if not ok:
        raise RuntimeError(
            "No hay dos fechas seleccionadas; evita el toast de 'No se ha seleccionado dos fechas'. "
            f"Valor actual del input: '{val or ''}'."
        )

    # --- 2) locate the button robustly -------------------------------------
    download_btn = page.locator(
        'button[title="Descargar Cotizaciones"], '
        'button[title*="Descargar"], '
        'button:has(.pi-download), '
        'button:has-text("Exportar")'
    ).first

    await download_btn.wait_for(timeout=timeout)
    # make sure it's in view even if header is sticky
    await download_btn.scroll_into_view_if_needed()

    # --- 3) click + wait for download, with one retry on toast -------------
    async def _try_click_and_download():
        return await click_and_download(page, lambda: download_btn.click())

    async def _toast_shows_no_range():
        # PrimeNG toasts usually are p-toastitem; match by message substring
        toast = page.locator("p-toastitem, .p-toast-message")
        return await toast.filter(has_text="No se ha seleccionado dos fechas").count() > 0

    try:
        return await _try_click_and_download()

    except Exception:
        # If the page complained about missing range, optionally reselect once and retry
        if await _toast_shows_no_range():
            if reselect is not None:
                await reselect()  # e.g., re-open datepicker and pick both dates again
                ok, _ = await _has_two_dates()
                if not ok:
                    raise RuntimeError("Re-selección de rango falló; aún no hay dos fechas.")
                return await _try_click_and_download()
            raise RuntimeError("El sitio mostró 'No se ha seleccionado dos fechas' tras el click.")
        # different failure; bubble up
        raise

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

        # 3) Trigger the export and capture the download
        xlsx_path = await download_with_range_guard(
        page,
        reselect=lambda: select_date_range_today_to_tomorrow(page)  # optional retry path
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