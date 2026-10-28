from datetime import timedelta

import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

TABLES = ["orders", "customers", "products", "promotions", "order_items", "promotion_usage"]

with DAG(
    dag_id="mysql_to_s3_prod",
    description="Ingest MySQL orders, customers, and products into PROD S3.",
    doc_md="""
    Ingest MySQL tables into the PROD S3 bucket.

    - Orders use incremental extraction with the PROD watermark.
    - Customers and products use full snapshots.
    - Each table runs independently.
    """,
    start_date=pendulum.datetime(2026, 10, 1, tz="America/Chicago"),
    schedule=None,  # Test manually before enabling the schedule.
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["mysql", "s3", "prod"],
) as dag:

    for table in TABLES:
        BashOperator(
            task_id=f"ingest_{table}",
            bash_command=(
                f"python -m src.ingestion.incremental_ingest --table {table}"
            ),
            env={
                "ENVIRONMENT": "prod",
                "S3_BUCKET": "cwo-prod-lake",
            },
            append_env=True,
        )