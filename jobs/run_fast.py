# jobs/run_fast.py
import asyncio
from db import init_db
from scrapers.fast_cotizador import run

if __name__ == "__main__":
    init_db()
    asyncio.run(run())
