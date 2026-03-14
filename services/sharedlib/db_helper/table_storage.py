import logging
from datetime import datetime

import os
import pandas as pd
from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient, TableServiceClient

from core.config import get_settings


def get_now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")


def format_timestamps_to_gmt8(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    for col in columns:
        if col in df.columns:
            try:
                # Convert to datetime and explicitly format to string with GMT+8 offset
                df[col] = pd.to_datetime(df[col], format="mixed", errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")
                # Clean up NaNs
                df[col] = df[col].where(pd.notnull(df[col]), None)
            except Exception:
                pass
    return df


def sanitize_key(key: object) -> str:
    if key is None or key == "":
        return "unknown"
    key_str = str(key)
    for ch in ["/", "\\", "#", "?"]:
        key_str = key_str.replace(ch, "_")
    return "".join(c for c in key_str if 31 < ord(c) < 127)


class DBHelper:
    def __init__(self, conn_str: str | None = None):
        self.key_map: dict[str, tuple[str | None, str]] = {
            "user": ("USER", "user_id"),
            "dim_role": ("ROLE", "role_id"),
            "dim_status": ("STATUS", "status_id"),
            "item": ("ITEM", "item_id"),
            "purchase_request": ("PR", "pr_id"),
            "purchase_order": ("PO", "po_id"),
            "supplier": ("SUPPLIER", "supplier_id"),
            "warehouse_stock": ("STOCK", "item_id"),
            "purchase_item_bridge": (None, "item_id"),
        }

        self.table_name_map: dict[str, str] = {
            "dim_role": "dimrole",
            "dim_status": "dimstatus",
            "purchase_request": "purchaserequest",
            "purchase_order": "purchaseorder",
            "warehouse_stock": "warehousestock",
            "purchase_item_bridge": "purchaseitembridge",
        }

        settings = get_settings()
        resolved = (
            conn_str
            or settings.azure_storage_connection_string
            or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        )
        if not resolved:
            logging.warning("AZURE_STORAGE_CONNECTION_STRING not set. DBHelper may fail.")
            self.service_client: TableServiceClient | None = None
        else:
            self.service_client = TableServiceClient.from_connection_string(resolved)

    def _get_table_client(self, table: str) -> TableClient:
        if not self.service_client:
            raise ConnectionError("Azure Storage Connection String not configured.")

        azure_table_name: str = self.table_name_map.get(table, table)
        table_client = self.service_client.get_table_client(azure_table_name)
        try:
            table_client.create_table()
        except Exception:
            pass
        return table_client

    def extract(self, table: str, fields: list[str] | None = None, conditions: dict | None = None):
        table_client = self._get_table_client(table)
        pk_val, rk_col = self.key_map.get(table, ("DATA", "id"))

        query = ""
        if pk_val:
            query = f"PartitionKey eq '{pk_val}'"

        if conditions:
            for key, value in conditions.items():
                filter_key = "RowKey" if key == rk_col else key
                sanitized_value = (
                    sanitize_key(value) if filter_key in ["PartitionKey", "RowKey"] else value
                )
                clause = (
                    f"{filter_key} eq '{sanitized_value}'"
                    if isinstance(sanitized_value, str)
                    else f"{filter_key} eq {value}"
                )
                query = f"({query}) and ({clause})" if query else clause

        try:
            entities = table_client.query_entities(query_filter=query) if query else table_client.list_entities()
            df = pd.DataFrame(list(entities))
        except Exception as exc:
            logging.error(f"Error extracting from {table}: {exc}")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        if rk_col:
            if "RowKey" in df.columns:
                df[rk_col] = df["RowKey"]

        cols_to_drop = ["PartitionKey", "RowKey", "Timestamp", "etag"]
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

        if fields:
            existing = [f for f in fields if f in df.columns]
            df = df[existing]

        return df

    def load(self, table: str, dataframe: pd.DataFrame, mode: str = "append") -> None:
        table_client = self._get_table_client(table)
        pk_val, rk_col = self.key_map.get(table, ("DATA", "id"))

        for _, row in dataframe.iterrows():
            entity = row.to_dict()

            if pk_val:
                entity["PartitionKey"] = pk_val
            elif "doc_id" in entity:
                entity["PartitionKey"] = sanitize_key(entity["doc_id"])
            else:
                entity["PartitionKey"] = "DATA"

            if rk_col in entity:
                entity["RowKey"] = sanitize_key(entity[rk_col])
            else:
                import uuid

                entity["RowKey"] = str(uuid.uuid4())

            for k, v in entity.items():
                if pd.isna(v):
                    entity[k] = None
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    if (isinstance(v, int) or (isinstance(v, float) and v.is_integer())) and (
                        v > 2147483647 or v < -2147483648
                    ):
                        entity[k] = str(int(v))
                    else:
                        entity[k] = v

            table_client.upsert_entity(entity)

    def modify(self, table: str, update_values: dict, conditions: dict) -> None:
        df = self.extract(table, conditions=conditions)
        if df.empty:
            return

        for col, val in update_values.items():
            df[col] = val

        if "last_modified_at" in df.columns:
            df["last_modified_at"] = get_now()

        self.load(table, df)

    def delete(self, table: str, conditions: dict) -> None:
        table_client = self._get_table_client(table)
        df = self.extract(table, conditions=conditions)
        if df.empty:
            return

        pk_val, rk_col = self.key_map.get(table, ("DATA", "id"))
        for _, row in df.iterrows():
            rk = sanitize_key(row[rk_col])
            pk = pk_val if pk_val else sanitize_key(row["doc_id"])
            try:
                table_client.delete_entity(partition_key=pk, row_key=rk)
            except ResourceNotFoundError:
                pass

    def upsert(self, table: str, new_df: pd.DataFrame, id_col: str) -> None:
        self.load(table, new_df)
