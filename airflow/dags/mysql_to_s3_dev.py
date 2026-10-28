from datetime import timedelta
import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

TABLES = ["orders", "customers", "products", "promotions", "order_items", "promotion_usage"]

with DAG(
    dag_id="mysql_to_s3_dev",
    description="Incrementally ingest MySQL orders, customers, and products into DEV S3.",
    doc_md="""
    Daily incremental extract of MySQL tables to the DEV S3 bucket.

    - Each table runs independently; one failure does not block the others.
    - Watermarks are managed by `src.ingestion.incremental_ingest` and advance
      only after a successful S3 write, so clearing a failed task is safe.
    """,
    start_date=pendulum.datetime(2026, 10, 1, tz="America/Chicago"),
    schedule="0 8 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["mysql", "s3", "dev"],
) as dag:

    for table in TABLES:
        BashOperator(
            task_id=f"ingest_{table}",
            bash_command=f"python -m src.ingestion.incremental_ingest --table {table}",
        )
