import os
import json
import urllib.request
import urllib.error
from . import config  # noqa: F401

def refresh_delta_table(host, token, warehouse_id, target_path):
    """Triggers a Databricks SQL query to create or replace the Delta table from the Volume CSV."""
    # Handle both raw ID (faea85fdea5744e5) and full HTTP path (/sql/1.0/warehouses/faea85fdea5744e5)
    warehouse_id = warehouse_id.split("/")[-1]
    print(f"🔄 Triggering Databricks Delta table refresh on warehouse {warehouse_id}...")
    
    clean_path = target_path.strip("/")
    parts = clean_path.split("/")
    if len(parts) < 4 or parts[0].lower() != "volumes":
        print(f"⚠️ Could not parse Unity Catalog Volume path from: {target_path}. Skipping table refresh.")
        return

    catalog = parts[1]
    schema = parts[2]
    volume = parts[3]
    filename = "/".join(parts[4:])

    # Table name matches the manual creation name
    table_name = "airtable_data"
    full_table_path = f"{catalog}.{schema}.{table_name}"
    
    # Using read_files, matching the parameters from the manual UI configuration (CSV, header, multiLine, escape)
    # We enable 'delta.columnMapping.mode' = 'name' to support spaces and special characters in column names
    sql_statement = f"""
    CREATE OR REPLACE TABLE {full_table_path}
    TBLPROPERTIES (
      'delta.columnMapping.mode' = 'name',
      'delta.minReaderVersion' = '2',
      'delta.minWriterVersion' = '5'
    )
    AS
    SELECT * FROM read_files(
      '/Volumes/{catalog}/{schema}/{volume}/{filename}',
      format => 'csv',
      header => true,
      inferSchema => true,
      multiLine => true,
      escape => '"'
    )
    """

    url = f"{host}/api/2.0/sql/statements"
    payload = {
        "warehouse_id": warehouse_id,
        "statement": sql_statement,
        "catalog": catalog,
        "schema": schema
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as response:
            if 200 <= response.status < 300:
                resp_data = json.loads(response.read().decode("utf-8"))
                state = resp_data.get("status", {}).get("state", "UNKNOWN")
                print(f"✅ SQL Statement submitted successfully. Execution state: {state}")
                if state == "FAILED":
                    err_msg = resp_data.get("status", {}).get("error", {}).get("message", "Unknown error")
                    print(f"❌ Table refresh failed: {err_msg}")
                else:
                    print(f"🎉 Delta table '{full_table_path}' successfully scheduled/updated!")
            else:
                print(f"❌ SQL execution request failed with status: {response.status}")
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error during SQL execution: {e.code} - {e.reason}")
        try:
            error_details = e.read().decode("utf-8")
            print(f"   Details: {error_details}")
        except Exception:
            pass
    except Exception as e:
        print(f"❌ Unexpected error during SQL execution: {e}")

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
            if 200 <= response.status < 300:
                print(f"✅ Successfully uploaded to Databricks Volume: {target_path}")
                
                # Check if we should also refresh the Delta table
                warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
                if warehouse_id:
                    refresh_delta_table(host, token, warehouse_id, target_path)
                else:
                    print("ℹ️ DATABRICKS_WAREHOUSE_ID not set. Skipping Delta table refresh.")
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
