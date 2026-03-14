import os
import io

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
    item_master = db.extract("item", fields=["item_id", "item_name"])
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
        return result[["item_id", "item_name", "quantity"]].to_dict(orient="records")

    return merged_df[["item_id", "item_name", "quantity"]].to_dict(orient="records")

