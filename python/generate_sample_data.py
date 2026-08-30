"""
E-commerce Clickstream Data Generator for Testing & Validation
Generates synthetic e-commerce clickstream data matching the Kaggle eCommerce schema:
- event_time, event_type, product_id, category_id, category_code, brand, price, user_id, user_session
"""

import os
import random
import uuid
from datetime import datetime, timedelta
import polars as pl

CATEGORIES = [
    ("electronics.smartphone", 1001, 150.0, 1200.0),
    ("electronics.audio.headphone", 1002, 25.0, 300.0),
    ("appliances.kitchen.refrigerators", 1003, 300.0, 2500.0),
    ("computers.notebook", 1004, 400.0, 3500.0),
    ("apparel.shoes", 1005, 40.0, 200.0),
    ("auto.accessories", 1006, 15.0, 150.0),
]

BRANDS = ["apple", "samsung", "xiaomi", "lg", "asus", "nike", "bosch"]

def generate_ecommerce_data(num_users: int = 500, days: int = 60, seed: int = 42) -> pl.DataFrame:
    random.seed(seed)
    start_date = datetime(2024, 1, 1, 0, 0, 0)
    
    rows = []
    
    for u_idx in range(1, num_users + 1):
        user_id = 100000 + u_idx
        # User first active date within the date window
        user_start_offset = random.randint(0, days - 15)
        first_event_date = start_date + timedelta(days=user_start_offset, hours=random.randint(8, 20))
        
        # User activity lifespan (how many sessions over weeks)
        num_sessions = random.choices([1, 2, 3, 5, 8, 12], weights=[40, 25, 15, 10, 7, 3])[0]
        
        current_time = first_event_date
        
        for s_idx in range(num_sessions):
            session_id = str(uuid.uuid4())
            cat_code, cat_id, min_p, max_p = random.choice(CATEGORIES)
            brand = random.choice(BRANDS)
            product_id = random.randint(50000, 99999)
            price = round(random.uniform(min_p, max_p), 2)
            
            # Session length (1 to 6 events)
            num_views = random.randint(1, 4)
            for _ in range(num_views):
                rows.append({
                    "event_time": current_time,
                    "event_type": "view",
                    "product_id": product_id,
                    "category_id": cat_id,
                    "category_code": cat_code,
                    "brand": brand,
                    "price": price,
                    "user_id": user_id,
                    "user_session": session_id
                })
                current_time += timedelta(seconds=random.randint(10, 180))
            
            # Cart probability (40%)
            if random.random() < 0.4:
                rows.append({
                    "event_time": current_time,
                    "event_type": "cart",
                    "product_id": product_id,
                    "category_id": cat_id,
                    "category_code": cat_code,
                    "brand": brand,
                    "price": price,
                    "user_id": user_id,
                    "user_session": session_id
                })
                current_time += timedelta(seconds=random.randint(15, 120))
                
                # Purchase probability given Cart (50%)
                if random.random() < 0.5:
                    rows.append({
                        "event_time": current_time,
                        "event_type": "purchase",
                        "product_id": product_id,
                        "category_id": cat_id,
                        "category_code": cat_code,
                        "brand": brand,
                        "price": price,
                        "user_id": user_id,
                        "user_session": session_id
                    })
                    current_time += timedelta(seconds=random.randint(5, 60))
            
            # Gap to next session (hours/days)
            gap_days = random.choices([0, 1, 3, 7, 14, 21, 30], weights=[20, 30, 20, 15, 8, 5, 2])[0]
            gap_hours = random.randint(1, 12)
            current_time += timedelta(days=gap_days, hours=gap_hours)
            
            if current_time > start_date + timedelta(days=days):
                break

    df = pl.DataFrame(rows)
    # Sort chronologically
    df = df.sort("event_time")
    return df

if __name__ == "__main__":
    output_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(output_dir, "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    
    print("Generating synthetic clickstream data with Polars...")
    df = generate_ecommerce_data(num_users=1000, days=90)
    
    csv_path = os.path.join(data_dir, "sample_raw_events.csv")
    parquet_path = os.path.join(data_dir, "sample_raw_events.parquet")
    
    df.write_csv(csv_path)
    df.write_parquet(parquet_path)
    
    print(f"Generated {len(df)} rows across {df['user_id'].n_unique()} unique users.")
    print(f"Saved CSV to: {csv_path}")
    print(f"Saved Parquet to: {parquet_path}")
