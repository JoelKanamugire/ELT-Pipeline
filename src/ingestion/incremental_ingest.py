import json
import os
from datetime import datetime, timezone
from io import BytesIO
from .table_config import TABLE_CONFIG

import boto3
import pandas as pd
import pymysql
from dotenv import load_dotenv
import argparse


load_dotenv()


ENVIRONMENT = os.environ["ENVIRONMENT"]
S3_BUCKET = os.environ["S3_BUCKET"]
WATERMARK_KEY = "control/watermarks/mysql/orders.json"



def read_watermark(watermark_key: str) -> str:
    s3_client = boto3.client("s3")

    response = s3_client.get_object(
        Bucket=S3_BUCKET,
        Key=watermark_key,
    )

    watermark_data = json.loads(
        response["Body"].read().decode("utf-8")
    )

    last_watermark = watermark_data["last_successful_watermark"]

    print(f"Current watermark: {last_watermark}")

    return last_watermark


def extract_table(config: dict, last_watermark: str | None = None,) -> pd.DataFrame:
          
     table_name = config["name"]
     primary_key = config["primary_key"]
     load_type = config["load_type"]
     watermark_column = config["watermark_column"]

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
         if load_type == "incremental":
             if last_watermark is None:
                 raise ValueError(
                     f"A watermark is required for incremental table {table_name}."
                 )
             query = f"""
                SELECT *
                FROM `{table_name}`
                WHERE `{watermark_column}` > %s
                ORDER BY `{watermark_column}`, `{primary_key}` ;
             """ 
             params = (last_watermark,)
            
         elif load_type == "full_snapshot":
             query = f"""
                SELECT *
                FROM `{table_name}`
                ORDER BY `{primary_key}`;
             """
             
             params = ()
        
         else:
             raise ValueError(f"Unsupported load type: {load_type}")
         
         with connection.cursor() as cursor:
             cursor.execute(query, params)
             rows = cursor.fetchall()
        
         dataframe = pd.DataFrame(rows) 
         print(
             f"Extracted {len(dataframe)} records "
             f"from {table_name}. "
         )
         
         return dataframe            
     finally:
        connection.close()


def convert_to_parquet(dataframe: pd.DataFrame, ) -> BytesIO:
          
          parquet_buffer = BytesIO()

          dataframe.to_parquet(
               parquet_buffer, 
               engine="pyarrow", 
               index=False,
          )

          parquet_buffer.seek(0)
          print(f"Converted {len(dataframe)} records to "
                f"{parquet_buffer.getbuffer().nbytes} Parquet bytes."
          )
          return parquet_buffer
    
def upload_to_s3(parquet_buffer: BytesIO, table_name:str, s3_prefix: str, ) -> str:
    s3_client = boto3.client("s3")
    now = datetime.now(timezone.utc)
    
    ingestion_date = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%S-%f")
    
    s3_key = (
        f"{s3_prefix}/"
        f"ingestion_date = {ingestion_date}/"
        f"{table_name}_{timestamp}.parquet"
    )
    parquet_buffer.seek(0)
    
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
    table_name: str, 
    watermark_key: str, 
    new_watermark: str,) -> None:
    
    s3_client = boto3.client("s3")
    
    watermark_data = {
        "table" : table_name,
        "last_successful_watermark": new_watermark,
    }
    
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key =watermark_key,
        Body=json.dumps(watermark_data, indent=2),
        ContentType = "application/json",    
    )
    print(f"Watermark updated to : {new_watermark}")
    
    
    
def run_table(config: dict) -> None:
    last_watermark = None

    if config["load_type"] == "incremental":
        last_watermark = read_watermark(
            watermark_key=config["watermark_key"],
        )

    dataframe = extract_table(
        config=config,
        last_watermark=last_watermark,
    )

    if dataframe.empty:
        print(
            f"No records found for {config['name']}. "
            "Nothing uploaded."
        )
        return

    parquet_buffer = convert_to_parquet(dataframe)

    s3_key = upload_to_s3(
        parquet_buffer=parquet_buffer,
        table_name=config["name"],
        s3_prefix=config["s3_prefix"],
    )

    validate_uploaded_file(
        s3_key=s3_key,
        expected_row_count=len(dataframe),
    )

    if config["load_type"] == "incremental":
        watermark_column = config["watermark_column"]

        new_watermark = (
            pd.to_datetime(dataframe[watermark_column].max())
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        update_watermark(
            table_name=config["name"],
            watermark_key=config["watermark_key"],
            new_watermark=new_watermark,
        )

    print(
        f"{config['load_type']} load for "
        f"{config['name']} completed successfully."
    )
    
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a configured MySQL table into S3."
    )

    parser.add_argument(
        "--table",
        required=True,
        choices=TABLE_CONFIG.keys(),
        help="Table to ingest.",
    )

    args = parser.parse_args()
    config = TABLE_CONFIG[args.table]

    run_table(config)


if __name__ == "__main__":
    main()