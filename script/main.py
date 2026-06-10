import asyncio
from playwright.async_api import async_playwright
import os

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

# Charge les variables d'environnement au démarrage
load_dotenv()

async def scrape_airtable_csv():
    url = os.getenv("AIRTABLE_URL")
    password = os.getenv("AIRTABLE_PASSWORD")

    if not url or not password:
        raise ValueError("Erreur: Les variables d'environnement AIRTABLE_URL et AIRTABLE_PASSWORD doivent être définies (par exemple dans un fichier .env)")

    print("🚀 Lancement du navigateur...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("🌐 Chargement de la page Airtable...")
        await page.goto(url)
        
        # 1ère gestion (Page de connexion en français)
        try:
            accept_button = page.locator('button', has_text='Tout accepter')
            if await accept_button.is_visible(timeout=3000):
                await accept_button.click()
        except Exception:
            pass

        max_tentatives = 3
        table_chargee = False

        print("🔑 Début du cycle d'authentification...")
        for tentative in range(max_tentatives):
            print(f"🔄 Tentative {tentative + 1}/{max_tentatives}...")
            try:
                champ_mdp = page.locator('input[type="password"]')
                if await champ_mdp.is_visible(timeout=5000):
                    await champ_mdp.fill(password)
                    await page.keyboard.press("Enter")
                
                print("⏳ Attente du chargement de la table...")
                await page.wait_for_selector('.table, .dataRow, #tableContainer', timeout=10000)
                
                print("✅ Table chargée !")
                table_chargee = True
                break 
                
            except Exception:
                print(f"⚠️ Échec lors de la tentative {tentative + 1}.")
                await asyncio.sleep(2)

        if not table_chargee:
            print("❌ Impossible de charger la table. Lancement de l'inspecteur...")
            await page.pause()
            await browser.close()
            return

        # --- VOTRE SÉLECTEUR EXACT EST INTÉGRÉ ICI ---
        print("🍪 Vérification de la pop-up de cookies Transcend 'Accept All'...")
        try:
            btn_cookies_en = page.get_by_role("button", name="Accept All")
            # On lui laisse 5 secondes max pour apparaître
            if await btn_cookies_en.is_visible(timeout=5000):
                await btn_cookies_en.click()
                print("✅ 'Accept All' cliqué et pop-up fermée !")
                # Petite pause pour que la page redevienne cliquable
                await asyncio.sleep(1) 
            else:
                print("ℹ️ Pas de bouton 'Accept All' détecté.")
        except Exception:
            pass
            
        print("📥 Recherche du menu d'options (...) et du bouton de téléchargement...")
        try:
            print("👉 Ouverture du menu '...'")
            bouton_menu = page.get_by_role("button", name="More view options")
            await bouton_menu.click()
            
            await asyncio.sleep(1)
            
            print("👉 Clic sur 'Download CSV'")
            bouton_download = page.get_by_role("menuitem", name="Download CSV")
            
            async with page.expect_download(timeout=10000) as download_info:
                await bouton_download.click() 
            
            download = await download_info.value
            file_path = os.path.join(os.getcwd(), "donnees_airtable.csv")
            await download.save_as(file_path)
            print(f"🎉 BINGO ! Fichier téléchargé avec succès ici : {file_path}")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'interaction avec le menu : {e}")
            await page.pause()

        print("Fermeture du navigateur dans 5 secondes...")
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_airtable_csv())