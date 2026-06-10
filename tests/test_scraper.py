import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from airtable_databricks_ingestion.scraper import scrape_airtable_csv

class AwaitableMock:
    """A helper class to mock an awaitable return value without requiring an active event loop."""
    def __init__(self, value):
        self.value = value
    def __await__(self):
        async def _async_func():
            return self.value
        return _async_func().__await__()

@pytest.fixture
def mock_playwright(mocker):
    """Fixture to mock all hierarchical async Playwright components."""
    mock_download = AsyncMock()
    mock_download.save_as = AsyncMock()

    mock_download_info = MagicMock()
    mock_download_info.value = AwaitableMock(mock_download)

    mock_expect_download_cm = MagicMock()
    mock_expect_download_cm.__aenter__ = AsyncMock(return_value=mock_download_info)
    mock_expect_download_cm.__aexit__ = AsyncMock(return_value=None)

    mock_locator = AsyncMock()
    mock_locator.is_visible = AsyncMock(return_value=True)
    mock_locator.click = AsyncMock()
    mock_locator.fill = AsyncMock()

    mock_keyboard = AsyncMock()
    mock_keyboard.press = AsyncMock()

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.locator = MagicMock(return_value=mock_locator)
    mock_page.keyboard = mock_keyboard
    mock_page.wait_for_selector = AsyncMock()
    mock_page.get_by_role = MagicMock(return_value=mock_locator)
    mock_page.expect_download = MagicMock(return_value=mock_expect_download_cm)

    mock_browser = AsyncMock()
    mock_browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser.close = AsyncMock()

    mock_chromium = AsyncMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_p = MagicMock()
    mock_p.chromium = mock_chromium

    mock_ap_cm = MagicMock()
    mock_ap_cm.__aenter__ = AsyncMock(return_value=mock_p)
    mock_ap_cm.__aexit__ = AsyncMock(return_value=None)

    mocker.patch(
        "airtable_databricks_ingestion.scraper.async_playwright",
        return_value=mock_ap_cm
    )
    
    return {
        "playwright": mock_p,
        "chromium": mock_chromium,
        "browser": mock_browser,
        "page": mock_page,
        "locator": mock_locator,
        "keyboard": mock_keyboard,
        "download": mock_download,
        "expect_download": mock_page.expect_download,
    }

@pytest.mark.asyncio
async def test_scrape_missing_credentials():
    """Test that ValueError is raised if credentials are not in environment."""
    with pytest.raises(ValueError, match="AIRTABLE_URL and AIRTABLE_PASSWORD environment variables must be defined"):
        await scrape_airtable_csv()

@pytest.mark.asyncio
async def test_scrape_airtable_csv_success(mocker, mock_playwright):
    """Test successful scraping and download orchestration flow."""
    os.environ["AIRTABLE_URL"] = "https://airtable.com/shrfake"
    os.environ["AIRTABLE_PASSWORD"] = "shhh-password"
    
    mock_upload = mocker.patch("airtable_databricks_ingestion.scraper.upload_to_databricks")
    
    await scrape_airtable_csv()
    
    mock_playwright["chromium"].launch.assert_called_once_with(headless=False)
    mock_playwright["page"].goto.assert_called_once_with("https://airtable.com/shrfake")
    mock_playwright["locator"].fill.assert_called_once_with("shhh-password")
    mock_playwright["keyboard"].press.assert_called_once_with("Enter")
    mock_playwright["download"].save_as.assert_called_once()
    mock_upload.assert_called_once()

@pytest.mark.asyncio
async def test_scrape_headless_resolution(mocker, mock_playwright):
    """Test headless resolution with different environment settings."""
    os.environ["AIRTABLE_URL"] = "https://airtable.com/shrfake"
    os.environ["AIRTABLE_PASSWORD"] = "shhh-password"
    mocker.patch("airtable_databricks_ingestion.scraper.upload_to_databricks")
    
    # 1. CI environment -> headless=True
    os.environ["CI"] = "true"
    await scrape_airtable_csv()
    mock_playwright["chromium"].launch.assert_called_with(headless=True)
    
    # 2. HEADLESS environment overrides CI
    os.environ["HEADLESS"] = "false"
    await scrape_airtable_csv()
    mock_playwright["chromium"].launch.assert_called_with(headless=False)

@pytest.mark.asyncio
async def test_scrape_table_not_loaded(mocker, mock_playwright):
    """Test that authentication retries 3 times and raises RuntimeError on failure."""
    os.environ["AIRTABLE_URL"] = "https://airtable.com/shrfake"
    os.environ["AIRTABLE_PASSWORD"] = "shhh-password"
    os.environ["CI"] = "true"
    
    # Mock wait_for_selector to fail
    mock_playwright["page"].wait_for_selector.side_effect = Exception("Page load timed out")
    
    # Avoid real sleep in tests
    mocker.patch("asyncio.sleep", return_value=None)
    
    with pytest.raises(RuntimeError, match="Unable to load the Airtable table after authentication"):
        await scrape_airtable_csv()
        
    assert mock_playwright["page"].wait_for_selector.call_count == 3
    assert mock_playwright["browser"].close.call_count == 1
