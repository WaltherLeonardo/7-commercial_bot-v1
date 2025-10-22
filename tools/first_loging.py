# tools/first_login.py
import asyncio
from scrapers.base import BrowserSession

async def main():
    async with BrowserSession(headless=False) as b:
        page = b.page
        await page.goto("https://cotizadorvehiculos.grupopana.com.pe/")
        print("\n>>> Please log in manually (including 2FA).")
        print(">>> Once you reach the dashboard/home screen, press ENTER here to finish.\n")

        # 🟢 This line makes the script wait until you press ENTER in the terminal
        input(">>> Waiting for you to finish login... press ENTER when ready.\n")

        print("✅ Login process complete. You can close the browser window now.")

if __name__ == "__main__":
    asyncio.run(main())