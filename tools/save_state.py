# tools/save_state.py
import os, asyncio
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
URL = os.getenv("CLASSIC_URL")  # or FAST_URL
STATE_PATH = Path("data/state.json")
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)   # visible window
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        await page.goto(URL)

        print("\n>>> Log in manually (including 2FA).")
        print(">>> When the app shows you are authenticated (dashboard/home), press ENTER here…")
        input()  # wait for you

        # Optional: verify you’re truly logged in by checking a selector that's only visible when authenticated
        # await page.wait_for_selector('text="Mi Dashboard"')

        await context.storage_state(path=STATE_PATH.as_posix())
        print(f"Saved session to: {STATE_PATH}")

        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
