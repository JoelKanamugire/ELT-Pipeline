from datetime import timedelta
import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator


with DAG(
    dag_id="mysql_to_s3_dev",
    description="Ingest MySQL orders and customers into DEV S3.",
    start_date=pendulum.datetime(2026, 10, 1, tz="America/Chicago"),
    schedule="0 20 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "execution_timeout": timedelta(minutes=30),
    },
    tags=["mysql", "s3", "dev"],
) as dag:
    
    ingest_orders = BashOperator(
        task_id="ingest_orders",
        bash_command=(
            "python -m src.ingestion.incremental_ingest --table orders"
        ),
    )
    
    ingest_customers = BashOperator(
        task_id="ingest_customers",
        bash_command=(
            "python -m src.ingestion.incremental_ingest --table customers"
        ),
    )
    ingest_products = BashOperator(
        task_id = "ingest_products", 
        bash_command=(
            "python -m src.ingestion.incremental_ingest --table products"
        ),
    )
    
    ingest_orders >> ingest_customers >> ingest_products
