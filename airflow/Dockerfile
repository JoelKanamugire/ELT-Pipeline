FROM apache/airflow:3.3.1

COPY requirements.txt /opt/airflow/requirements.txt

RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /opt/airflow/requirements.txt