import os

import pandas as pd

from services.sharedlib.db_helper.db_helper import DBHelper, get_now
from services.sharedlib.exceptions import NotFoundException


db = DBHelper()


def update_inventory(incoming_csv_path: str | None) -> str:
    if not incoming_csv_path or not os.path.exists(incoming_csv_path):
        raise NotFoundException("Error: Incoming file not found.")

    new_stock_df = pd.read_csv(incoming_csv_path)
    new_stock_df["last_updated_at"] = get_now()
    db.upsert("warehouse_stock", new_stock_df, id_col="item_id")
    updated_full_df = db.extract("warehouse_stock")
    return updated_full_df.to_csv(index=False)


def count_inventory(item_name: str | None = None):
    stock_df = db.extract("warehouse_stock")
    item_master = db.extract("item", fields=["item_id", "item_name"])
    merged_df = stock_df.merge(item_master, on="item_id", how="left")

    if item_name:
        result = merged_df[merged_df["item_name"].str.lower() == item_name.lower()]
        if not result.empty:
            return int(result.iloc[0]["quantity"])
        return 0

    return merged_df.set_index("item_name")["quantity"].to_dict()

