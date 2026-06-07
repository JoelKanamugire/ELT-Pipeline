import random
import mysql.connector
from faker import Faker
from tqdm import tqdm

fake = Faker()

# Source 1: existing ecommerce MySQL
core_conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3307,
    user="pipeline_user",
    password="pipeline123",
    database="ecommerce"
)

core_cursor = core_conn.cursor()
core_cursor.execute("SELECT product_id FROM products")
product_ids = [row[0] for row in core_cursor.fetchall()]

print(f"Found {len(product_ids)} product IDs from source 1")

# Source 2: metadata MySQL
meta_conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3308,
    user="pipeline_user",
    password="pipeline123",
    database="product_metadata_db"
)

meta_cursor = meta_conn.cursor()

meta_cursor.execute("""
CREATE TABLE IF NOT EXISTS product_metadata (
    metadata_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT UNIQUE,
    brand VARCHAR(100),
    rating DECIMAL(2,1),
    review_count INT,
    supplier VARCHAR(100),
    warranty_months INT,
    is_active BOOLEAN,
    last_updated DATETIME
)
""")

brands = ["Nike", "Apple", "Samsung", "Sony", "Adidas", "Dell", "HP", "LG"]
suppliers = ["Supplier A", "Supplier B", "Supplier C", "Supplier D"]

metadata = []

for product_id in tqdm(product_ids):
    metadata.append((
        product_id,
        random.choice(brands),
        round(random.uniform(2.5, 5.0), 1),
        random.randint(0, 10000),
        random.choice(suppliers),
        random.choice([6, 12, 24, 36]),
        random.choice([True, True, True, False]),
        fake.date_time_between(start_date="-1y", end_date="now")
    ))

meta_cursor.executemany("""
INSERT INTO product_metadata (
    product_id,
    brand,
    rating,
    review_count,
    supplier,
    warranty_months,
    is_active,
    last_updated
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    brand = VALUES(brand),
    rating = VALUES(rating),
    review_count = VALUES(review_count),
    supplier = VALUES(supplier),
    warranty_months = VALUES(warranty_months),
    is_active = VALUES(is_active),
    last_updated = VALUES(last_updated)
""", metadata)

meta_conn.commit()

print(f"Inserted/updated {len(metadata)} metadata records")

core_cursor.close()
core_conn.close()

meta_cursor.close()
meta_conn.close()