TABLE_CONFIG = {
    "orders": {
        "name": "orders",
        "primary_key": "order_id",
        "load_type": "incremental",
        "watermark_column": "updated_at",
        "s3_prefix": "raw/mysql/orders",
        "watermark_key": "control/watermarks/mysql/orders.json",
    },
    
    
     "customers": {
        "name": "customers",
        "primary_key": "customer_id",
        "load_type": "full_snapshot",
        "watermark_column": None,
        "s3_prefix": "raw/mysql/customers",
        "watermark_key": None,
    },
     
        "products": {
        "name": "products",
        "primary_key": "product_id",
        "load_type": "full_snapshot",
        "watermark_column": None,
        "s3_prefix": "raw/mysql/products",
        "watermark_key": None,
    },
}