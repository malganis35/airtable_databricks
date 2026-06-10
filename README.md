# Airtable CSV Ingestion Script

An automated ingestion script to download shared Airtable tables as CSV files. Using Playwright, this script automatically handles password authentication, cookies selection, and navigation to download the latest view data.

## Features
- **Automatic Authentication**: Inputs password on the Airtable share view.
- **Transcend Cookie Consent Handling**: Closes the "Accept All" cookie banner automatically.
- **CSV Exporter Navigation**: Opens the View Options (`More view options`) menu and triggers `Download CSV`.
- **Environment Isolation**: Securely loads target URL and passwords from a `.env` file.
- **Databricks Upload**: Automatically uploads the downloaded CSV directly to a Databricks Volume using Databricks Workspace Files API.

---

## Prerequisites

Make sure you have the following installed on your machine:
- **Python**: version 3.12 or newer.
- **uv**: A fast Python package installer and resolver. (If you don't have it, install it via: `curl -LsSf https://astral.sh/uv/install.sh | sh`).

---

## Getting Started

### 1. Installation

First, install the Python package dependencies:
```bash
uv sync
```

Next, download and install the required browser binaries for Playwright:
```bash
uv run playwright install chromium
```

### 2. Configuration

Create your `.env` configuration file by duplicating the provided template:
```bash
cp .env.template .env
```

Open the newly created `.env` file and set your target Airtable URL and credentials:
```env
AIRTABLE_URL="https://airtable.com/your-shared-view-url"
AIRTABLE_PASSWORD="your-airtable-password"

# Optional Databricks Upload Configuration (required if uploading to Databricks)
DATABRICKS_HOST="https://your-databricks-instance.cloud.databricks.com"
DATABRICKS_TOKEN="dapi..."
DATABRICKS_TARGET_PATH="/Volumes/mon_catalogue/mon_schema/mes_fichiers/airtable_data.csv"
```

> [!IMPORTANT]
> The `.env` file contains sensitive credentials. It is automatically ignored by Git (via `.gitignore`) so it won't be committed to version control.

### 3. Execution

Run the main scraping script:
```bash
uv run airtable-databricks-ingestion
```

### What to Expect
1. A Chromium browser window will open.
2. It will navigate to your shared Airtable URL.
3. It will attempt to input the password and hit Enter.
4. Once the table displays, it will close the cookie banner if present.
5. It will locate the "More view options" menu, click it, and trigger "Download CSV".
6. The downloaded file will be saved in the root folder as `airtable_data.csv`.
7. **(Optional)** If Databricks variables are configured, the script will upload the file directly to your Databricks Volume.
8. The browser closes automatically after 5 seconds.

---

## Databricks Unity Catalog Setup

To upload the downloaded CSV file to Databricks, you must configure a Catalog, Schema, and Volume in your Databricks workspace.

You can execute the following SQL commands in a Databricks Notebook or SQL Editor (requires appropriate Unity Catalog creation privileges):

```sql
-- 1. Create the Catalog
CREATE CATALOG IF NOT EXISTS mon_catalogue;

-- 2. Create the Schema inside the Catalog
CREATE SCHEMA IF NOT EXISTS mon_catalogue.mon_schema;

-- 3. Create the Managed Volume to store the CSV files
CREATE VOLUME IF NOT EXISTS mon_catalogue.mon_schema.mes_fichiers;
```

> [!NOTE]
> Make sure that the path specified in your `DATABRICKS_TARGET_PATH` environment variable matches these entities:
> `/Volumes/<catalog>/<schema>/<volume>/<filename.csv>`

### Required Token Permissions (Unity Catalog)

Databricks Personal Access Tokens (PAT) do not use OAuth-style granular scopes. Instead, the token inherits all permissions of the user or Service Principal that created it. 

To successfully upload files, the token's identity must be granted the following privileges in Databricks Unity Catalog:
- **`USE CATALOG`** on the destination catalog (e.g., `mon_catalogue`)
- **`USE SCHEMA`** on the destination schema (e.g., `mon_schema`)
- **`WRITE VOLUME`** on the destination managed volume (e.g., `mes_fichiers`)

Example SQL to grant these privileges if needed:
```sql
GRANT USE CATALOG ON CATALOG mon_catalogue TO `user_or_group`;
GRANT USE SCHEMA ON SCHEMA mon_catalogue.mon_schema TO `user_or_group`;
GRANT WRITE VOLUME ON VOLUME mon_catalogue.mon_schema.mes_fichiers TO `user_or_group`;
```

### Delta Table Ingestion (`airtable_data`)

Once the CSV file is uploaded to the Volume, you can load it (for the first time) or update it (completely overwrite/replace) into a Delta Table in the same schema.

#### Option A: Automated Table Refresh (via Python Script)
If you configure a SQL Warehouse ID, the script will automatically trigger the Databricks SQL Statement Execution API to refresh the Delta table (`airtable_data`) immediately after uploading the CSV.

1. Go to **SQL Warehouses** in Databricks and select your warehouse (e.g. *Serverless Starter Warehouse*).
2. Under **Connection details**, locate the **SQL Warehouse ID** (a 16-character hexadecimal string).
3. Add it to your `.env` file or GitLab CI/CD variables:
   ```env
   DATABRICKS_WAREHOUSE_ID="your-16-character-id"
   ```

#### Option B: Manual/Scheduled Ingestion (via Databricks Notebook / SQL Editor)
You can run this SQL query manually or as a scheduled workflow inside Databricks:
```sql
CREATE OR REPLACE TABLE training_db.feedback.airtable_data AS
SELECT * FROM read_files(
  '/Volumes/training_db/feedback/raw_files/airtable_data.csv',
  format => 'csv',
  header => true,
  inferSchema => true,
  multiLine => true,
  escape => '"'
);
```

---

## GitLab CI/CD Pipeline

This project includes a pre-configured `.gitlab-ci.yml` pipeline that automates the extraction and loading process.

### CI/CD Pipeline Optimizations
- **Browser Caching**: The pipeline uses the pre-installed Playwright browser binaries in the `mcr.microsoft.com/playwright/python` Docker image (`PLAYWRIGHT_BROWSERS_PATH: "/ms-playwright"`), avoiding the need to download browsers during pipeline runs.
- **Dependency Caching**: Caches `.venv` and `uv` packages between pipeline runs to speed up execution.

### Setup Instructions
To enable the pipeline, configure the following **CI/CD Variables** in your GitLab repository (**Settings > CI/CD > Variables**):

| Variable Name | Description | Example / Format |
|---|---|---|
| `AIRTABLE_URL` | The shared view URL to scrape | `https://airtable.com/...` |
| `AIRTABLE_PASSWORD` | The password for the Airtable view | `Caotri...` (Masked & Hidden) |
| `DATABRICKS_HOST` | The Databricks workspace instance hostname | `https://dbc-xxxx.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | A personal access token for Databricks API access | `dapi...` (Masked & Hidden) |
| `DATABRICKS_TARGET_PATH` | *(Optional)* Target path on Databricks Volume | `/Volumes/my_catalog/my_schema/my_volume/airtable_data.csv` |

### Scheduling the Ingestion (Daily)

To run the pipeline automatically once a day:
1. In your GitLab project on the web, go to **Build > Pipeline schedules** (or **CI/CD > Schedules**).
2. Click **New schedule**.
3. Configure the schedule:
   - **Description**: `Daily Airtable to Databricks Ingestion`
   - **Interval Pattern**: Select **Daily** (or enter a custom Cron expression like `0 2 * * *` to run at 2 AM daily).
   - **Target branch**: `main`
4. Click **Save pipeline schedule**.