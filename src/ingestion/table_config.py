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
        "order_items": {
            "name": "order_items", 
            "primary_key": "item_id", 
            "load_type": "incremental",
            "watermark_column": "updated_at",
            "s3_prefix": "raw/mysql/order_items",
            "watermark_key": "control/watermarks/mysql/order_items.json",          
        },
        "promotions": {
            "name": "promotions",
            "primary_key": "promo_id",
            "load_type": "full_snapshot",
            "watermark_column": None,
            "s3_prefix": "raw/mysql/promotions",
            "watermark_key": None,
        }, 
        "promotion_usage":{
            "name": "promotion_usage", 
            "primary_key": "usage_id",
            "load_type": "incremental",
            "watermark_column": "updated_at",
            "s3_prefix": "raw/mysql/promotion_usage",
            "watermark_key": "control/watermarks/mysql/promotion_usage.json",       
        }
}