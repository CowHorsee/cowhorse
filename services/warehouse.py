import os
import io

import pandas as pd

from services.sharedlib.db_helper.db_helper import DBHelper, get_now
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

