import os

def load_dotenv(dotenv_path=None):
    """Loads environment variables from a .env file if it exists."""
    if dotenv_path is None:
        possible_paths = [
            os.path.join(os.getcwd(), ".env"),
            # Relative path from src/airtable_databricks_ingestion/config.py to root directory
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
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

# Automatically load environment variables when configuration module is imported
load_dotenv()
