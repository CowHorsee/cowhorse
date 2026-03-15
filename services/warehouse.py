import os
import io
import random

import pandas as pd

from services.sharedlib.db_helper.db_helper import DBHelper, get_now, format_timestamps_to_gmt8
from services.sharedlib.exceptions import BadRequestException, NotFoundException


db = DBHelper()


def update_inventory(csv_content: str | None) -> str:
    if not csv_content:
        raise BadRequestException("Error: CSV content is empty.")

    try:
        new_stock_df = pd.read_csv(io.StringIO(csv_content))
    except Exception as e:
        raise BadRequestException(f"Error: Invalid CSV format. {str(e)}")

    required_columns = ["item_id", "quantity"]
    missing_cols = [col for col in required_columns if col not in new_stock_df.columns]
    if missing_cols:
        raise BadRequestException(f"Error: CSV schema mismatch. Missing columns: {', '.join(missing_cols)}")

    new_stock_df["last_updated_at"] = get_now()
    db.upsert("warehouse_stock", new_stock_df, id_col="item_id")
    updated_full_df = db.extract("warehouse_stock")
    updated_full_df = format_timestamps_to_gmt8(updated_full_df, ["last_updated_at"])
    return updated_full_df.to_csv(index=False)


def count_inventory(query: str | None = None):
    stock_df = db.extract("warehouse_stock")
    item_master = db.extract("item", fields=["item_id", "item_name", "unit_price"])
    merged_df = stock_df.merge(item_master, on="item_id", how="left")

    merged_df["item_name"] = merged_df["item_name"].fillna("").astype(str)
    merged_df["item_id"] = merged_df["item_id"].fillna("").astype(str)
    merged_df["quantity"] = merged_df["quantity"].fillna(0).astype(int)

    if query:
        query_lower = query.lower()
        mask = (
            merged_df["item_name"].str.lower().str.contains(query_lower) |
            merged_df["item_id"].str.lower().str.contains(query_lower)
        )
        result = merged_df[mask]
        return result[["item_id", "item_name", "quantity", "unit_price"]].to_dict(orient="records")

    return merged_df[["item_id", "item_name", "quantity", "unit_price"]].to_dict(orient="records")


def get_graph_datapoint(item_name: str, year: int, month: int | None = None):
    now = pd.to_datetime(get_now())
    current_year = now.year
    current_month = now.month
    
    # If month is not provided, default to current month for the range end
    target_month = month if month is not None else current_month
    
    if year > current_year or (year == current_year and target_month > current_month):
        raise BadRequestException("Error: Cannot predict demand for future months beyond the current month.")

    # 1. Get warehouse inventory count (current stock)
    inventory_items = count_inventory(query=item_name)
    count_in_warehouse = 0
    actual_item_name = item_name
    if inventory_items:
        # Assuming the first match is the desired item
        count_in_warehouse = inventory_items[0].get("quantity", 0)
        actual_item_name = inventory_items[0].get("item_name", item_name)

    dummy_sales_data = {
        "Elba Built-in Gas Hob": {1: 45, 2: 52},
        "Faber Chimney Hood": {1: 88, 2: 95},
        "Rubine Electric Oven": {1: 15, 2: 12},
        "Haustern Kitchen Sink": {1: 30, 2: 28},
        "Tuscani Wine Chiller": {1: 5, 2: 8},
        "Ceiling Fan 56-inch": {1: 40, 2: 35},
        "Instant Water Heater": {1: 22, 2: 18},
        "Freestanding Dishwasher": {1: 10, 2: 14},
        "Smart Air Purifier": {1: 12, 2: 9},
        "Induction Cooker": {1: 25, 2: 30},
        "Microwave Oven 25L": {1: 18, 2: 20},
        "Refrigerator Side-by-Side": {1: 7, 2: 11},
        "Digital Door Lock": {1: 33, 2: 29},
        "Rubine Cooker Hood": {1: 65, 2: 58},
        "Sorento Kitchen Faucet": {1: 20, 2: 25}
    }

    datapoints = []
    for m in range(1, target_month + 1):
        # 2. Predicted Demand (random for now based on item, year, month)
        random.seed(f"predict_{actual_item_name}_{year}_{m}")
        predicted_demand = random.randint(10, 200)

        dp = {
            "item_name": actual_item_name,
            "year": year,
            "month": m,
            "inventory_count": count_in_warehouse,
            "predicted_demand": predicted_demand,
        }

        # 3. Actual sales logic (Only for Jan and Feb 2026)
        is_past_month = (year < current_year) or (year == current_year and m < current_month)
        # However, user specifically asked for "actual sales for jan and feb"
        if is_past_month and m in [1, 2]:
            item_sales = dummy_sales_data.get(actual_item_name, {})
            actual_sales = item_sales.get(m)
            
            if actual_sales is None:
                # Fallback if not in dummy data
                random.seed(f"actual_{actual_item_name}_{year}_{m}")
                actual_sales = random.randint(5, int(predicted_demand * 1.2))
                
            dp["actual_sales"] = actual_sales
        
        datapoints.append(dp)
        
    return datapoints

