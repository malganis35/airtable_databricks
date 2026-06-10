import os
import urllib.request
import urllib.error
from . import config  # noqa: F401

def upload_to_databricks(file_path):
    """Uploads the local CSV file to Databricks Volume using the Workspace Files API."""
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
