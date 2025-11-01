# jobs/run_classic.py
import sys, os, asyncio
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db import init_db
from scrapers.classic_cotizador import run

if __name__ == "__main__":
    init_db()
    asyncio.run(run())
    print("🦗🦗")