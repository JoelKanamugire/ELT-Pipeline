import json
from io import BytesIO
from unittest.mock import Mock

import pandas as pd
import pytest
from botocore.exceptions import ClientError

from src.ingestion import incremental_ingest as ingest


WATERMARK_KEY = "control/watermarks/mysql/orders.json"
REQUIRED_CONFIG_KEYS = {
    "name",
    "primary_key",
    "load_type",
    "watermark_column",
    "s3_prefix",
    "watermark_key",
}


class FakeS3:
    """In-memory stand-in for the boto3 S3 client."""

    class exceptions:
        # read_watermark catches s3_client.exceptions.NoSuchKey, so this
        # must be a real exception class (a Mock attribute is not).
        class NoSuchKey(Exception):
            pass

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        if isinstance(Body, str):
            Body = Body.encode("utf-8")
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise self.exceptions.NoSuchKey(Key)
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}


@pytest.fixture
def fake_s3(monkeypatch):
    """Route every boto3.client("s3") call in the module to one FakeS3."""
    s3 = FakeS3()
    monkeypatch.setattr(ingest, "boto3", Mock(client=Mock(return_value=s3)))
    return s3


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


def orders_frame(*timestamps):
    config = ingest.TABLE_CONFIG["orders"]
    return pd.DataFrame({
        config["primary_key"]: list(range(1, len(timestamps) + 1)),
        config["watermark_column"]: list(timestamps),
    })


# ---------------------------------------------------------------------------
# Pipeline orchestration (run_table)
# ---------------------------------------------------------------------------

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
        new_watermark="2026-09-04 12:00:00.000000",
    )


def test_first_run_without_watermark_loads_everything(steps):
    config = ingest.TABLE_CONFIG["orders"]
    steps["read_watermark"].return_value = None
    steps["extract_table"].return_value = orders_frame(
        pd.Timestamp("2026-09-02 10:00:00"),
        pd.Timestamp("2026-09-03 08:30:00"),
    )

    ingest.run_table(config)

    # No watermark means a full extract, and the first watermark gets saved.
    steps["extract_table"].assert_called_once_with(
        config=config,
        last_watermark=None,
    )
    steps["update_watermark"].assert_called_once_with(
        table_name=config["name"],
        watermark_key=config["watermark_key"],
        new_watermark="2026-09-03 08:30:00.000000",
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


def test_upload_failure_does_not_update_watermark(steps):
    steps["extract_table"].return_value = orders_frame(
        pd.Timestamp("2026-09-04 12:00:00"),
    )
    steps["upload_to_s3"].side_effect = ConnectionError("S3 unreachable")

    with pytest.raises(ConnectionError):
        ingest.run_table(ingest.TABLE_CONFIG["orders"])

    steps["validate_uploaded_file"].assert_not_called()
    steps["update_watermark"].assert_not_called()


def test_extract_failure_does_not_upload_or_update_watermark(steps):
    steps["extract_table"].side_effect = ConnectionError("MySQL unreachable")

    with pytest.raises(ConnectionError):
        ingest.run_table(ingest.TABLE_CONFIG["orders"])

    steps["upload_to_s3"].assert_not_called()
    steps["update_watermark"].assert_not_called()


def test_null_watermark_timestamp_stops_before_upload(steps):
    steps["extract_table"].return_value = orders_frame(
        pd.Timestamp("2026-09-04 12:00:00"),
        None,
    )

    with pytest.raises(ValueError, match="null timestamps"):
        ingest.run_table(ingest.TABLE_CONFIG["orders"])

    steps["upload_to_s3"].assert_not_called()
    steps["update_watermark"].assert_not_called()


def test_unparseable_watermark_timestamp_stops_before_upload(steps):
    steps["extract_table"].return_value = orders_frame(
        "2026-09-04 12:00:00",
        "not-a-date",
    )

    with pytest.raises(ValueError):
        ingest.run_table(ingest.TABLE_CONFIG["orders"])

    steps["upload_to_s3"].assert_not_called()
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


@pytest.mark.parametrize("table", ingest.TABLE_CONFIG.keys())
def test_every_configured_table_runs(steps, table):
    config = ingest.TABLE_CONFIG[table]
    data = {config["primary_key"]: [1]}
    if config["load_type"] == "incremental":
        data[config["watermark_column"]] = pd.to_datetime(
            ["2026-09-04 12:00:00"]
        )
    steps["extract_table"].return_value = pd.DataFrame(data)

    ingest.run_table(config)

    upload_kwargs = steps["upload_to_s3"].call_args.kwargs
    assert upload_kwargs["table_name"] == table
    assert upload_kwargs["s3_prefix"] == config["s3_prefix"]
    assert steps["update_watermark"].called == (
        config["load_type"] == "incremental"
    )


# ---------------------------------------------------------------------------
# Watermark storage (read_watermark / update_watermark)
# ---------------------------------------------------------------------------

def test_watermark_round_trip(fake_s3):
    ingest.update_watermark(
        table_name="orders",
        watermark_key=WATERMARK_KEY,
        new_watermark="2026-09-04 12:00:00.000000",
    )

    assert ingest.read_watermark(WATERMARK_KEY) == "2026-09-04 12:00:00.000000"

    stored = json.loads(fake_s3.objects[(ingest.S3_BUCKET, WATERMARK_KEY)])
    assert stored == {
        "table": "orders",
        "last_successful_watermark": "2026-09-04 12:00:00.000000",
    }


def test_missing_watermark_file_returns_none(fake_s3):
    assert ingest.read_watermark(WATERMARK_KEY) is None


@pytest.mark.parametrize("bad_value", ["", "   ", None, 123])
def test_invalid_watermark_value_raises(fake_s3, bad_value):
    fake_s3.put_object(
        Bucket=ingest.S3_BUCKET,
        Key=WATERMARK_KEY,
        Body=json.dumps({"last_successful_watermark": bad_value}),
    )

    with pytest.raises(ValueError, match="Invalid watermark"):
        ingest.read_watermark(WATERMARK_KEY)


def test_watermark_file_without_watermark_field_raises(fake_s3):
    fake_s3.put_object(
        Bucket=ingest.S3_BUCKET,
        Key=WATERMARK_KEY,
        Body=json.dumps({"table": "orders"}),
    )

    # Must fail loudly rather than fall back to a full reload.
    with pytest.raises(KeyError):
        ingest.read_watermark(WATERMARK_KEY)


def test_s3_access_error_is_not_treated_as_missing_watermark(fake_s3):
    # Only NoSuchKey may mean "start fresh". Anything else returning None
    # would silently trigger a full reload of the table.
    fake_s3.get_object = Mock(side_effect=ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
        "GetObject",
    ))

    with pytest.raises(ClientError):
        ingest.read_watermark(WATERMARK_KEY)


# ---------------------------------------------------------------------------
# TABLE_CONFIG
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table", ingest.TABLE_CONFIG.keys())
def test_table_config_is_valid(table):
    config = ingest.TABLE_CONFIG[table]

    assert set(config) == REQUIRED_CONFIG_KEYS
    assert config["name"] == table
    assert config["primary_key"]
    assert config["s3_prefix"] == f"raw/mysql/{table}"
    assert config["load_type"] in {"incremental", "full_snapshot"}

    if config["load_type"] == "incremental":
        assert config["watermark_column"]
        assert config["watermark_key"] == (
            f"control/watermarks/mysql/{table}.json"
        )


def test_watermark_keys_are_unique():
    keys = [
        config["watermark_key"]
        for config in ingest.TABLE_CONFIG.values()
        if config["watermark_key"] is not None
    ]

    assert len(keys) == len(set(keys))
