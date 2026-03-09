import pandas as pd
import os
from sharedlib.db_helper.db_ops import DBHelper, get_now

# Initialize database helper
db = DBHelper()

def update_inventory(incoming_csv_path):
    """
    Receives a CSV path from ../warehouse, updates warehouse_stock.csv,
    and returns the updated content as a CSV string.
    """
    # 1. Read the new data from the warehouse folder
    # Expected format in incoming CSV: item_id, quantity
    if not os.path.exists(incoming_csv_path):
        return "Error: Incoming file not found."

    new_stock_df = pd.read_csv(incoming_csv_path)
    
    # 3. Update logic: If item exists in incoming, use new quantity; else keep old.
    # We use 'upsert' logic here to ensure we replace current values.
    # We add the required timestamp for the warehouse_stock table schema.
    new_stock_df['last_updated_at'] = get_now()
    
    # Perform the update (Upsert)
    db.upsert("warehouse_stock", new_stock_df, id_col="item_id")
    
    # 4. Return the fully updated table as a string
    updated_full_df = db.extract("warehouse_stock")
    return updated_full_df.to_csv(index=False)

def count_inventory(item_name=None):
    """
    Returns quantity for a specific name or the full dictionary of stock.
    """
    # 1. Extract necessary tables
    stock_df = db.extract("warehouse_stock")
    item_master = db.extract("item", fields=["item_id", "item_name"])
    
    # 2. Join tables to map Item Name to Quantity
    merged_df = stock_df.merge(item_master, on="item_id", how="left")
    
    # 3. Return logic
    if item_name:
        # Filter by name (case-insensitive)
        result = merged_df[merged_df['item_name'].str.lower() == item_name.lower()]
        if not result.empty:
            return int(result.iloc[0]['quantity'])
        return 0 # Item not found or 0 stock
    
    # If no name provided, return a dictionary of {name: quantity}
    return merged_df.set_index('item_name')['quantity'].to_dict()