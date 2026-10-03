import json
import os
from datetime import datetime, timezone
from io import BytesIO

import boto3
import pandas as pd
import pymysql
from dotenv import load_dotenv


load_dotenv()


ENVIRONMENT = os.environ["ENVIRONMENT"]
S3_BUCKET = os.environ["S3_BUCKET"]
WATERMARK_KEY = "control/watermarks/mysql/orders.json"



def read_watermark() -> str:
    s3_client = boto3.client("s3")

    response = s3_client.get_object(
        Bucket=S3_BUCKET,
        Key=WATERMARK_KEY,
    )

    watermark_data = json.loads(
        response["Body"].read().decode("utf-8")
    )

    last_watermark = watermark_data["last_successful_watermark"]

    print(f"Current watermark: {last_watermark}")

    return last_watermark


def extract_incremental_orders(
    last_watermark: str,
) -> pd.DataFrame:
    connection = pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        query = """
            SELECT *
            FROM orders
            WHERE updated_at > %s
            ORDER BY updated_at, order_id;
        """
        with connection.cursor() as cursor:
               cursor.execute(query, (last_watermark,))
               rows = cursor.fetchall()

        orders_df = pd.DataFrame(rows)

        print(f"Extracted {len(orders_df)} new or updated orders. "
              )

        return orders_df
            

    finally:
        connection.close()

def convert_to_parquet(orders_df: pd.DataFrame, ) -> BytesIO:
          
          parquet_buffer = BytesIO()

          orders_df.to_parquet(
               parquet_buffer, 
               engine="pyarrow", 
               index=False,
          )

          parquet_buffer.seek(0)
          print(f"Converted {len(orders_df)} orders to "
                f"{parquet_buffer.getbuffer().nbytes} Parquet bytes."
          )
          return parquet_buffer
    
def upload_to_s3(parquet_buffer: BytesIO,) -> str:
         s3_client = boto3.client("s3")
         now = datetime.now(timezone.utc)

         ingestion_date = now.strftime("%Y-%m-%d")
         timestamp = now.strftime("%Y%m%dT%H%M%SZ")

         s3_key = (
              f"raw/mysql/orders/"
              f"ingestion_date={ingestion_date}/"
              f"orders_timestamp_{timestamp}.parquet"
         )
         s3_client.upload_fileobj(
              parquet_buffer, 
              S3_BUCKET, 
              s3_key,
         )

         print(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")

         return s3_key


def validate_uploaded_file(s3_key: str, expected_row_count: int, )-> None:
         s3_client = boto3.client("s3")

         response = s3_client.get_object(
              Bucket=S3_BUCKET,
              Key = s3_key
         )

         uploaded_bytes = response["Body"].read()
         uploaded_df = pd.read_parquet(BytesIO(uploaded_bytes))
         actual_row_count = len(uploaded_df)

         if actual_row_count != expected_row_count:
            raise ValueError(
                 f"Row-count validation failed: "
                 f"expected {expected_row_count}, "
                 f"found {actual_row_count}. "
            )
         print(f"Validation successful: "
               f"{actual_row_count} rows found in s3."
               )
    
def update_watermark(
    new_watermark: str,
) -> None:
    s3_client = boto3.client("s3")

    watermark_data = {
        "table": "orders",
        "last_successful_watermark": new_watermark,
    }

    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=WATERMARK_KEY,
        Body=json.dumps(watermark_data, indent=2),
        ContentType="application/json",
    )

    print(f"Watermark updated to: {new_watermark}")

def main() -> None:
    last_watermark = read_watermark()

    orders_df = extract_incremental_orders(
        last_watermark=last_watermark,
    )

    if orders_df.empty:
        print("No new or updated orders. Nothing uploaded.")
        return

    parquet_buffer = convert_to_parquet(orders_df)
    s3_key = upload_to_s3(parquet_buffer)

    validate_uploaded_file(
        s3_key=s3_key,
        expected_row_count=len(orders_df),
    )

    new_watermark = (
        pd.to_datetime(orders_df["updated_at"].max())
        .strftime("%Y-%m-%d %H:%M:%S")
    )

    update_watermark(new_watermark)

    print("Incremental orders load to DEV completed successfully.")


if __name__ == "__main__":
    main()




