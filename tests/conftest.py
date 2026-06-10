import pytest
import os

@pytest.fixture(autouse=True)
def clean_environ():
    """Fixture to ensure environment variable isolation between tests."""
    orig_env = dict(os.environ)
    
    # Remove environment variables that our application relies on
    keys_to_clear = [
        "AIRTABLE_URL",
        "AIRTABLE_PASSWORD",
        "DATABRICKS_HOST",
        "DATABRICKS_TOKEN",
        "DATABRICKS_TARGET_PATH",
        "DATABRICKS_WAREHOUSE_ID",
        "HEADLESS",
        "CI",
    ]
    for key in keys_to_clear:
        os.environ.pop(key, None)
        
    yield
    
    # Restore original environment variables after the test
    os.environ.clear()
    os.environ.update(orig_env)
