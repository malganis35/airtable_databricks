import asyncio
from playwright.async_api import async_playwright
import os
import urllib.request
import urllib.error


def load_dotenv(dotenv_path=None):
    if dotenv_path is None:
        possible_paths = [
            os.path.join(os.getcwd(), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        ]
        for path in possible_paths:
            if os.path.exists(path):
                dotenv_path = path
                break
    
    if dotenv_path and os.path.exists(dotenv_path):
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    os.environ[key] = val

# Load environment variables at startup
load_dotenv()

def upload_to_databricks(file_path):
    host = os.getenv("DATABRICKS_HOST")
    token = os.getenv("DATABRICKS_TOKEN")
    # Default to the path requested by the user if not specified in env
    target_path = os.getenv("DATABRICKS_TARGET_PATH", "/Volumes/mon_catalogue/mon_schema/mes_fichiers/airtable_data.csv")

    if not host or not token:
        print("ℹ️ Databricks environment variables (DATABRICKS_HOST, DATABRICKS_TOKEN) not set. Skipping upload.")
        return

    print(f"☁️ Uploading {file_path} to Databricks...")
    if not host.startswith("https://"):
        host = f"https://{host}"

    # Ensure target path is formatted correctly for the endpoint (e.g. no leading slash)
    clean_path = target_path.lstrip("/")
    url = f"{host}/api/2.0/fs/files/{clean_path}"

    try:
        with open(file_path, "rb") as f:
            file_data = f.read()

        req = urllib.request.Request(
            url,
            data=file_data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream"
            },
            method="PUT"
        )

        with urllib.request.urlopen(req) as response:
            if response.status in (200, 201):
                print(f"✅ Successfully uploaded to Databricks Volume: {target_path}")
            else:
                print(f"❌ Upload failed with status code: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error during upload to Databricks: {e.code} - {e.reason}")
        try:
            error_details = e.read().decode("utf-8")
            print(f"   Details: {error_details}")
        except Exception:
            pass
        raise
    except Exception as e:
        print(f"❌ Unexpected error during upload to Databricks: {e}")
        raise

async def scrape_airtable_csv():
    url = os.getenv("AIRTABLE_URL")
    password = os.getenv("AIRTABLE_PASSWORD")

    if not url or not password:
        raise ValueError("Error: The AIRTABLE_URL and AIRTABLE_PASSWORD environment variables must be defined (e.g. in a .env file)")

    is_ci = os.getenv("CI") == "true"
    # Run headless in CI environment by default, or if HEADLESS is set to true
    headless_env = os.getenv("HEADLESS", "")
    if headless_env.lower() in ("true", "1"):
        headless = True
    elif headless_env.lower() in ("false", "0"):
        headless = False
    else:
        headless = is_ci

    print(f"🚀 Launching browser (headless={headless})...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        
        print("🌐 Loading Airtable page...")
        await page.goto(url)
        
        # First handling (French login page)
        try:
            accept_button = page.locator('button', has_text='Tout accepter')
            if await accept_button.is_visible(timeout=3000):
                await accept_button.click()
        except Exception:
            pass

        max_attempts = 3
        table_loaded = False

        print("🔑 Starting authentication cycle...")
        for attempt in range(max_attempts):
            print(f"🔄 Attempt {attempt + 1}/{max_attempts}...")
            try:
                champ_mdp = page.locator('input[type="password"]')
                if await champ_mdp.is_visible(timeout=5000):
                    await champ_mdp.fill(password)
                    await page.keyboard.press("Enter")
                
                print("⏳ Waiting for the table to load...")
                await page.wait_for_selector('.table, .dataRow, #tableContainer', timeout=10000)
                
                print("✅ Table loaded!")
                table_loaded = True
                break 
                
            except Exception:
                print(f"⚠️ Failed during attempt {attempt + 1}.")
                await asyncio.sleep(2)

        if not table_loaded:
            print("❌ Unable to load the table. Launching inspector...")
            if not is_ci:
                await page.pause()
            await browser.close()
            raise RuntimeError("Unable to load the Airtable table after authentication.")

        # --- YOUR EXACT SELECTOR IS INTEGRATED HERE ---
        print("🍪 Checking Transcend 'Accept All' cookie pop-up...")
        try:
            btn_cookies_en = page.get_by_role("button", name="Accept All")
            # Allow up to 5 seconds to appear
            if await btn_cookies_en.is_visible(timeout=5000):
                await btn_cookies_en.click()
                print("✅ 'Accept All' clicked and pop-up closed!")
                # Short pause to let the page become clickable again
                await asyncio.sleep(1) 
            else:
                print("ℹ️ No 'Accept All' button detected.")
        except Exception:
            pass
            
        print("📥 Looking for options menu (...) and download button...")
        try:
            print("👉 Opening the '...' menu")
            bouton_menu = page.get_by_role("button", name="More view options")
            await bouton_menu.click()
            
            await asyncio.sleep(1)
            
            print("👉 Clicking 'Download CSV'")
            bouton_download = page.get_by_role("menuitem", name="Download CSV")
            
            async with page.expect_download(timeout=10000) as download_info:
                await bouton_download.click() 
            
            download = await download_info.value
            file_path = os.path.join(os.getcwd(), "airtable_data.csv")
            await download.save_as(file_path)
            print(f"🎉 BINGO! File successfully downloaded to: {file_path}")
            
            # Upload the file to Databricks if configuration is present
            upload_to_databricks(file_path)
            
        except Exception as e:
            print(f"❌ Error during execution: {e}")
            if not is_ci:
                await page.pause()
            raise

        print("Closing browser in 5 seconds...")
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_airtable_csv())