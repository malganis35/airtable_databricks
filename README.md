# Airtable CSV Ingestion Script

An automated ingestion script to download shared Airtable tables as CSV files. Using Playwright, this script automatically handles password authentication, cookies selection, and navigation to download the latest view data.

## Features
- **Automatic Authentication**: Inputs password on the Airtable share view.
- **Transcend Cookie Consent Handling**: Closes the "Accept All" cookie banner automatically.
- **CSV Exporter Navigation**: Opens the View Options (`More view options`) menu and triggers `Download CSV`.
- **Environment Isolation**: Securely loads target URL and passwords from a `.env` file.

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
```

> [!IMPORTANT]
> The `.env` file contains sensitive credentials. It is automatically ignored by Git (via `.gitignore`) so it won't be committed to version control.

### 3. Execution

Run the main scraping script:
```bash
uv run script/main.py
```

### What to Expect
1. A Chromium browser window will open.
2. It will navigate to your shared Airtable URL.
3. It will attempt to input the password and hit Enter.
4. Once the table displays, it will close the cookie banner if present.
5. It will locate the "More view options" menu, click it, and trigger "Download CSV".
6. The downloaded file will be saved in the root folder as `airtable_data.csv`.
7. The browser closes automatically after 5 seconds.