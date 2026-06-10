import os
from airtable_databricks_ingestion.config import load_dotenv

def test_load_dotenv_custom_path(tmp_path):
    """Test loading dotenv from a valid custom path with comments, spaces, and quotes."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TEST_VAR1=hello\n"
        "  TEST_VAR2 = 'world' \n"
        "TEST_VAR3=\"quotes\"\n"
        "# This is a comment line\n"
        "  # Another comment line with spaces\n"
        "\n" # Empty line
        "TEST_VAR4 = value_with_=__and_quotes\n"
    )
    
    # Run load_dotenv with the temp path
    load_dotenv(dotenv_path=str(env_file))
    
    assert os.environ.get("TEST_VAR1") == "hello"
    assert os.environ.get("TEST_VAR2") == "world"
    assert os.environ.get("TEST_VAR3") == "quotes"
    assert os.environ.get("TEST_VAR4") == "value_with_=__and_quotes"

def test_load_dotenv_non_existent_file():
    """Test loading from a file path that doesn't exist does not raise errors."""
    initial_env_count = len(os.environ)
    load_dotenv(dotenv_path="/nonexistent/path/to/.env")
    assert len(os.environ) == initial_env_count
