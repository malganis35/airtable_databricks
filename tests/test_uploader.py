import os
import json
import pytest
from urllib.error import HTTPError
from io import BytesIO
from airtable_databricks_ingestion.uploader import refresh_delta_table, upload_to_databricks

def test_refresh_delta_table_invalid_path(capsys):
    """Test that refresh_delta_table returns early if the path does not start with /Volumes."""
    refresh_delta_table(
        host="https://fake-host.databricks.com",
        token="fake-token",
        warehouse_id="fake-warehouse",
        target_path="/Invalid/catalog/schema/volume/file.csv"
    )
    captured = capsys.readouterr()
    assert "Skipping table refresh" in captured.out

def test_refresh_delta_table_success(mocker, capsys):
    """Test successful submission of a refresh SQL statement to Databricks API."""
    mock_response = mocker.MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = json.dumps({"status": {"state": "SUCCEEDED"}}).encode("utf-8")
    
    mocker.patch("urllib.request.urlopen", return_value=mock_response)
    mock_request = mocker.patch("urllib.request.Request")
    
    refresh_delta_table(
        host="https://fake-host.databricks.com",
        token="fake-token",
        warehouse_id="/sql/1.0/warehouses/warehouse-123",
        target_path="/Volumes/my_catalog/my_schema/my_vol/sub/file.csv"
    )
    
    # Verify urllib.request.Request was constructed correctly
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert args[0] == "https://fake-host.databricks.com/api/2.0/sql/statements"
    assert kwargs["headers"]["Authorization"] == "Bearer fake-token"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["method"] == "POST"
    
    # Verify the payload content
    sent_data = json.loads(kwargs["data"].decode("utf-8"))
    assert sent_data["warehouse_id"] == "warehouse-123"
    assert sent_data["catalog"] == "my_catalog"
    assert sent_data["schema"] == "my_schema"
    assert "CREATE OR REPLACE TABLE my_catalog.my_schema.airtable_data" in sent_data["statement"]
    assert "'/Volumes/my_catalog/my_schema/my_vol/sub/file.csv'" in sent_data["statement"]
    
    captured = capsys.readouterr()
    assert "successfully scheduled/updated" in captured.out

def test_refresh_delta_table_failed_state(mocker, capsys):
    """Test when SQL submission succeeds but state returns FAILED."""
    mock_response = mocker.MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = json.dumps({
        "status": {
            "state": "FAILED",
            "error": {"message": "Invalid SQL syntax"}
        }
    }).encode("utf-8")
    
    mocker.patch("urllib.request.urlopen", return_value=mock_response)
    mocker.patch("urllib.request.Request")
    
    refresh_delta_table(
        host="https://fake-host.databricks.com",
        token="fake-token",
        warehouse_id="warehouse-123",
        target_path="/Volumes/my_catalog/my_schema/my_vol/file.csv"
    )
    
    captured = capsys.readouterr()
    assert "Table refresh failed: Invalid SQL syntax" in captured.out

def test_refresh_delta_table_http_error(mocker, capsys):
    """Test HTTP Error handling in refresh_delta_table."""
    fp = BytesIO(b"Detail error message from API")
    mock_err = HTTPError("url", 401, "Unauthorized", {}, fp)
    mocker.patch("urllib.request.urlopen", side_effect=mock_err)
    mocker.patch("urllib.request.Request")
    
    refresh_delta_table(
        host="https://fake-host.databricks.com",
        token="fake-token",
        warehouse_id="warehouse-123",
        target_path="/Volumes/my_catalog/my_schema/my_vol/file.csv"
    )
    
    captured = capsys.readouterr()
    assert "HTTP Error during SQL execution: 401 - Unauthorized" in captured.out
    assert "Details: Detail error message from API" in captured.out

def test_upload_to_databricks_missing_env(capsys):
    """Test that upload is skipped when Databricks credentials are not set."""
    upload_to_databricks("some_file.csv")
    captured = capsys.readouterr()
    assert "Skipping upload" in captured.out

def test_upload_to_databricks_success(mocker, tmp_path, capsys):
    """Test successful file upload and check that Delta Table refresh is triggered if warehouse ID is set."""
    os.environ["DATABRICKS_HOST"] = "fake-host.databricks.com"
    os.environ["DATABRICKS_TOKEN"] = "fake-token"
    os.environ["DATABRICKS_TARGET_PATH"] = "/Volumes/my_cat/my_sch/my_vol/test.csv"
    os.environ["DATABRICKS_WAREHOUSE_ID"] = "warehouse-abc"
    
    # Create fake CSV file to upload
    csv_file = tmp_path / "airtable_data.csv"
    csv_file.write_text("col1,col2\nval1,val2")
    
    mock_response = mocker.MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response
    mocker.patch("urllib.request.urlopen", return_value=mock_response)
    mock_request = mocker.patch("urllib.request.Request")
    
    mock_refresh = mocker.patch("airtable_databricks_ingestion.uploader.refresh_delta_table")
    
    upload_to_databricks(str(csv_file))
    
    # Verify PUT request construction
    mock_request.assert_called_once()
    args, kwargs = mock_request.call_args
    assert args[0] == "https://fake-host.databricks.com/api/2.0/fs/files/Volumes/my_cat/my_sch/my_vol/test.csv"
    assert kwargs["headers"]["Authorization"] == "Bearer fake-token"
    assert kwargs["headers"]["Content-Type"] == "application/octet-stream"
    assert kwargs["method"] == "PUT"
    assert kwargs["data"] == b"col1,col2\nval1,val2"
    
    # Verify Delta table refresh was called
    mock_refresh.assert_called_once_with(
        "https://fake-host.databricks.com",
        "fake-token",
        "warehouse-abc",
        "/Volumes/my_cat/my_sch/my_vol/test.csv"
    )
    
    captured = capsys.readouterr()
    assert "Successfully uploaded to Databricks Volume" in captured.out

def test_upload_to_databricks_http_error(mocker, tmp_path):
    """Test that HTTPError during upload is logged and reraised."""
    os.environ["DATABRICKS_HOST"] = "https://fake-host.databricks.com"
    os.environ["DATABRICKS_TOKEN"] = "fake-token"
    
    csv_file = tmp_path / "airtable_data.csv"
    csv_file.write_text("data")
    
    fp = BytesIO(b"details of failure")
    mock_err = HTTPError("url", 500, "Internal Server Error", {}, fp)
    mocker.patch("urllib.request.urlopen", side_effect=mock_err)
    mocker.patch("urllib.request.Request")
    
    with pytest.raises(HTTPError):
        upload_to_databricks(str(csv_file))
