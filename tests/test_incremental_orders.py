from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest

from ingestion import incremental_ingest


@patch.object(incremental_ingest, "update_watermark")
@patch.object(incremental_ingest, "validate_uploaded_file")
@patch.object(incremental_ingest, "upload_to_s3")
@patch.object(incremental_ingest, "convert_to_parquet")
@patch.object(incremental_ingest, "extract_incremental_orders")
@patch.object(incremental_ingest, "read_watermark")
def test_main_successful_incremental_load(
    mock_read_watermark,
    mock_extract_orders,
    mock_convert_to_parquet,
    mock_upload_to_s3,
    mock_validate,
    mock_update_watermark,
):
    # Fake rows representing orders returned by MySQL.
    orders_df = pd.DataFrame(
        {
            "order_id": [101, 102],
            "updated_at": [
                "2026-09-04 10:00:00",
                "2026-09-04 11:30:00",
            ],
        }
    )

    fake_parquet_buffer = BytesIO(b"fake parquet data")
    fake_s3_key = (
        "raw/mysql/orders/"
        "ingestion_date=2026-09-04/"
        "orders_20260904T113000Z.parquet"
    )

    # Tell the fake functions what to return.
    mock_read_watermark.return_value = "2026-09-03 00:55:02"
    mock_extract_orders.return_value = orders_df
    mock_convert_to_parquet.return_value = fake_parquet_buffer
    mock_upload_to_s3.return_value = fake_s3_key

    # Run the real main() orchestration.
    incremental_ingest.main()

    # Check that extraction received the existing watermark.
    mock_extract_orders.assert_called_once_with(
    last_watermark="2026-09-03 00:55:02"
)

    # Check that the extracted orders were converted.
    mock_convert_to_parquet.assert_called_once_with(orders_df)

    # Check that the resulting buffer was uploaded.
    mock_upload_to_s3.assert_called_once_with(
        fake_parquet_buffer
    )

    # Check that two uploaded rows were expected.
    mock_validate.assert_called_once_with(
        s3_key=fake_s3_key,
        expected_row_count=2,
    )

    # Check that the newest updated_at became the watermark.
    mock_update_watermark.assert_called_once_with(
        "2026-09-04 11:30:00"
    )


@patch.object(incremental_ingest, "update_watermark")
@patch.object(incremental_ingest, "validate_uploaded_file")
@patch.object(incremental_ingest, "upload_to_s3")
@patch.object(incremental_ingest, "convert_to_parquet")
@patch.object(incremental_ingest, "extract_incremental_orders")
@patch.object(incremental_ingest, "read_watermark")
def test_main_does_nothing_when_no_orders_exist(
    mock_read_watermark,
    mock_extract_orders,
    mock_convert_to_parquet,
    mock_upload_to_s3,
    mock_validate,
    mock_update_watermark,
):
    mock_read_watermark.return_value = "2026-09-04 11:30:00"

    # Pretend MySQL returned zero incremental orders.
    mock_extract_orders.return_value = pd.DataFrame()

    incremental_ingest.main()

    # Nothing should happen after an empty extraction.
    mock_convert_to_parquet.assert_not_called()
    mock_upload_to_s3.assert_not_called()
    mock_validate.assert_not_called()
    mock_update_watermark.assert_not_called()


@patch.object(incremental_ingest, "update_watermark")
@patch.object(incremental_ingest, "validate_uploaded_file")
@patch.object(incremental_ingest, "upload_to_s3")
@patch.object(incremental_ingest, "convert_to_parquet")
@patch.object(incremental_ingest, "extract_incremental_orders")
@patch.object(incremental_ingest, "read_watermark")
def test_watermark_does_not_update_when_validation_fails(
    mock_read_watermark,
    mock_extract_orders,
    mock_convert_to_parquet,
    mock_upload_to_s3,
    mock_validate,
    mock_update_watermark,
):
    orders_df = pd.DataFrame(
        {
            "order_id": [101],
            "updated_at": ["2026-09-04 11:30:00"],
        }
    )

    mock_read_watermark.return_value = "2026-09-03 00:55:02"
    mock_extract_orders.return_value = orders_df
    mock_convert_to_parquet.return_value = BytesIO(
        b"fake parquet data"
    )
    mock_upload_to_s3.return_value = (
        "raw/mysql/orders/orders.parquet"
    )

    # Pretend validation discovered a problem.
    mock_validate.side_effect = ValueError(
        "Row-count validation failed"
    )

    with pytest.raises(
        ValueError,
        match="Row-count validation failed",
    ):
        incremental_ingest.main()

    # Failed validation must never move the watermark.
    mock_update_watermark.assert_not_called()