import random
from datetime import datetime, timedelta
from faker import Faker
import mysql.connector
from tqdm import tqdm

fake = Faker('en_US')

# ── DB connection ──────────────────────────────────────────
conn = mysql.connector.connect(
    host="127.0.0.1",
    port=3308,
    user="pipeline_user",
    password="pipeline123",
    database="product_catalog"
)
cursor = conn.cursor()

# ── Schema ─────────────────────────────────────────────────
cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
    category_id   INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) UNIQUE,
    description   TEXT,
    created_at    DATETIME
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id     INT AUTO_INCREMENT PRIMARY KEY,
    vendor_name   VARCHAR(255),
    email         VARCHAR(255) UNIQUE,
    phone         VARCHAR(50),
    city          VARCHAR(100),
    state         VARCHAR(50),
    zip_code      VARCHAR(20),
    rating        DECIMAL(3,2),
    status        VARCHAR(50),
    joined_date   DATETIME,
    total_sales   DECIMAL(12,2)
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id      INT AUTO_INCREMENT PRIMARY KEY,
    vendor_id       INT,
    category_id     INT,
    name            VARCHAR(255),
    brand           VARCHAR(100),
    description     TEXT,
    price           DECIMAL(10,2),
    stock_quantity  INT,
    sku             VARCHAR(100) UNIQUE,
    weight          DECIMAL(8,2),
    rating          DECIMAL(3,2),
    is_active       BOOLEAN,
    created_at      DATETIME,
    FOREIGN KEY (vendor_id)   REFERENCES vendors(vendor_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS product_reviews (
    review_id     INT AUTO_INCREMENT PRIMARY KEY,
    product_id    INT,
    customer_id   INT,
    rating        INT,
    comment       TEXT,
    review_date   DATETIME,
    helpful_votes INT,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
)""")

conn.commit()
print("✅ Schema created")

# ── Categories ─────────────────────────────────────────────
print("Generating categories...")
categories = [
    ("Electronics", "Computers, phones, gadgets and accessories"),
    ("Clothing", "Men and women fashion and apparel"),
    ("Books", "Fiction, non-fiction, textbooks and more"),
    ("Home & Garden", "Furniture, decor and garden supplies"),
    ("Sports", "Equipment and accessories for all sports"),
    ("Toys", "Games and toys for all ages"),
    ("Beauty", "Skincare, makeup and personal care"),
    ("Automotive", "Car parts, accessories and tools"),
    ("Food & Grocery", "Fresh and packaged food items"),
    ("Health", "Vitamins, supplements and medical supplies"),
    ("Office", "Office supplies, furniture and equipment"),
    ("Pet Supplies", "Food, toys and accessories for pets"),
]

cursor.executemany("""
    INSERT IGNORE INTO categories (name, description, created_at)
    VALUES (%s, %s, %s)
""", [(c[0], c[1], fake.date_time_between(start_date="-5y", end_date="-3y")) for c in categories])
conn.commit()
print(f"✅ {len(categories)} categories inserted")

# ── Vendors ────────────────────────────────────────────────
print("Generating vendors...")
us_states = ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI",
             "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI", "CO", "MN"]
statuses = ["active", "active", "active", "suspended", "pending"]
vendors = []

for _ in tqdm(range(10000)):
    vendors.append((
        fake.company(),
        fake.unique.company_email(),
        fake.phone_number()[:20],
        fake.city(),
        random.choice(us_states),
        fake.zipcode(),
        round(random.uniform(1.0, 5.0), 2),
        random.choice(statuses),
        fake.date_time_between(start_date="-5y", end_date="-1y"),
        round(random.uniform(1000, 10000000), 2)
    ))

cursor.executemany("""
    INSERT INTO vendors (vendor_name, email, phone, city, state, zip_code,
                        rating, status, joined_date, total_sales)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""", vendors)
conn.commit()
print(f"✅ {len(vendors)} vendors inserted")

# ── Products ───────────────────────────────────────────────
print("Generating products...")
brands = ["Samsung", "Apple", "Nike", "Adidas", "Sony", "LG", "Dell", "HP",
          "Zara", "H&M", "Levi's", "Canon", "Nikon", "Bose", "Under Armour",
          "Reebok", "Puma", "Logitech", "Razer", "Asus"]
products = []

for i in tqdm(range(100000)):
    products.append((
        random.randint(1, 10000),
        random.randint(1, 12),
        fake.catch_phrase(),
        random.choice(brands),
        fake.text(max_nb_chars=200),
        round(random.uniform(5.99, 1999.99), 2),
        random.randint(0, 5000),
        fake.unique.bothify(text='SKU-????-#####'),
        round(random.uniform(0.1, 50.0), 2),
        round(random.uniform(1.0, 5.0), 2),
        random.choice([True, True, True, False]),
        fake.date_time_between(start_date="-3y", end_date="now")
    ))
    if len(products) >= 10000:
        cursor.executemany("""
            INSERT INTO products (vendor_id, category_id, name, brand, description,
                                price, stock_quantity, sku, weight, rating,
                                is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, products)
        conn.commit()
        products = []

print("✅ Products inserted")

# ── Product Reviews ────────────────────────────────────────
print("Generating product reviews...")
reviews = []

for _ in tqdm(range(500000)):
    reviews.append((
        random.randint(1, 100000),
        random.randint(1, 100000),
        random.randint(1, 5),
        fake.text(max_nb_chars=300),
        fake.date_time_between(start_date="-2y", end_date="now"),
        random.randint(0, 500)
    ))
    if len(reviews) >= 10000:
        cursor.executemany("""
            INSERT INTO product_reviews (product_id, customer_id, rating,
                                        comment, review_date, helpful_votes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, reviews)
        conn.commit()
        reviews = []

print("✅ Product reviews inserted")

cursor.close()
conn.close()
print("\n🎉 Product catalog data generated successfully!")