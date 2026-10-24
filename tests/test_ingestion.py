from io import BytesIO
from unittest.mock import Mock

import pandas as pd
import pytest

from src.ingestion import incremental_ingest as ingest


@pytest.fixture
def steps(monkeypatch):
    """Replace database and S3 operations; keep real Parquet conversion."""
    mocks = {
        "read_watermark": Mock(return_value="2026-09-01 00:00:00"),
        "extract_table": Mock(),
        "convert_to_parquet": Mock(wraps=ingest.convert_to_parquet),
        "upload_to_s3": Mock(return_value="raw/mysql/orders/test.parquet"),
        "validate_uploaded_file": Mock(),
        "update_watermark": Mock(),
    }

    for name, mock in mocks.items():
        monkeypatch.setattr(ingest, name, mock)

    return mocks

def test_incremental_success(steps):
    config = ingest.TABLE_CONFIG["orders"]
    column = config["watermark_column"]

    # Put the newest timestamp first to verify we use max().
    dataframe = pd.DataFrame({
        config["primary_key"]: [1, 2],
        column: pd.to_datetime([
            "2026-09-04 12:00:00",
            "2026-09-02 10:00:00",
        ]),
    })
    steps["extract_table"].return_value = dataframe
    
    
    def validate(**kwargs):
        # The watermark must not advance before validation.
        steps["update_watermark"].assert_not_called()

    steps["validate_uploaded_file"].side_effect = validate

    ingest.run_table(config)

    steps["read_watermark"].assert_called_once_with(
        watermark_key=config["watermark_key"],
    )
    steps["extract_table"].assert_called_once_with(
        config=config,
        last_watermark="2026-09-01 00:00:00",
    )
    
     # Check that the uploaded buffer contains readable Parquet.
    buffer = steps["upload_to_s3"].call_args.kwargs["parquet_buffer"]
    actual = pd.read_parquet(BytesIO(buffer.getvalue()))
    pd.testing.assert_frame_equal(actual, dataframe)

    steps["validate_uploaded_file"].assert_called_once_with(
        s3_key="raw/mysql/orders/test.parquet",
        expected_row_count=2,
    )
    steps["update_watermark"].assert_called_once_with(
        table_name=config["name"],
        watermark_key=config["watermark_key"],
        new_watermark="2026-09-04 12:00:00",
    )
    
def test_empty_extraction_uploads_nothing(steps):
    steps["extract_table"].return_value = pd.DataFrame()

    ingest.run_table(ingest.TABLE_CONFIG["orders"])

    steps["convert_to_parquet"].assert_not_called()
    steps["upload_to_s3"].assert_not_called()
    steps["validate_uploaded_file"].assert_not_called()
    steps["update_watermark"].assert_not_called()
    
def test_validation_failure_does_not_update_watermark(steps):
    config = ingest.TABLE_CONFIG["orders"]
    steps["extract_table"].return_value = pd.DataFrame({
        config["primary_key"]: [1],
        config["watermark_column"]: pd.to_datetime([
            "2026-09-04 12:00:00",
        ]),
    })
    steps["validate_uploaded_file"].side_effect = ValueError(
        "Row-count validation failed"
    )

    with pytest.raises(ValueError, match="Row-count validation failed"):
        ingest.run_table(config)

    steps["upload_to_s3"].assert_called_once()
    steps["update_watermark"].assert_not_called()
    
def test_snapshot_does_not_use_watermarks(steps):
    config = ingest.TABLE_CONFIG["customers"]
    steps["extract_table"].return_value = pd.DataFrame({
        config["primary_key"]: [1, 2],
    })

    ingest.run_table(config)

    steps["extract_table"].assert_called_once_with(
        config=config,
        last_watermark=None,
    )
    steps["upload_to_s3"].assert_called_once()
    steps["validate_uploaded_file"].assert_called_once()
    steps["read_watermark"].assert_not_called()
    steps["update_watermark"].assert_not_called()

