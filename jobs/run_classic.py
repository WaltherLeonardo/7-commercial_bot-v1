# jobs/run_classic.py
import sys, os, asyncio
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # add project root to import path

from db import init_db
from scrapers.classic_cotizador import run  # async def run(): ... uses BrowserSession

if __name__ == "__main__":
    # Make sure Chrome is running with: chrome --remote-debugging-port=9222
    # And DEBUG_URL is set in .env (or defaults to http://localhost:9222 in base.py)
    init_db()
    asyncio.run(run())