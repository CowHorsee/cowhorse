import pandas as pd
import os
import logging
from datetime import datetime
from azure.data.tables import TableServiceClient, TableClient
from azure.core.exceptions import ResourceNotFoundError

# Utility to get current timestamp
def get_now():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")

# Utility to sanitize PartitionKey and RowKey for Azure Table Storage
def sanitize_key(key):
    if not key:
        return "unknown"
    key = str(key)
    # PartitionKey and RowKey cannot contain: / \ # ? or control characters
    forbidden = ['/', '\\', '#', '?']
    for char in forbidden:
        key = key.replace(char, '_')
    # Remove control characters
    return "".join(c for c in key if 31 < ord(c) < 127)

class DBHelper:
    def __init__(self):
        # Configuration for PartitionKey and RowKey mapping
        # table_name -> (PartitionKey, RowKeySourceColumn)
        self.key_map = {
            "user": ("USER", "user_id"),
            "dim_role": ("ROLE", "role_id"),
            "dim_status": ("STATUS", "status_id"),
            "item": ("ITEM", "item_id"),
            "purchase_request": ("PR", "pr_id"),
            "purchase_order": ("PO", "po_id"),
            "supplier": ("SUPPLIER", "supplier_id"),
            "warehouse_stock": ("STOCK", "item_id"),
            "purchase_item_bridge": (None, "item_id")
        }

        # Alphanumeric mapping for Azure Table naming constraints
        self.table_name_map = {
            "dim_role": "dimrole",
            "dim_status": "dimstatus",
            "purchase_request": "purchaserequest",
            "purchase_order": "purchaseorder",
            "warehouse_stock": "warehousestock",
            "purchase_item_bridge": "purchaseitembridge"
        }
        
        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            # Fallback for local testing if needed, though plan says migrate to Azure
            logging.warning("AZURE_STORAGE_CONNECTION_STRING not set. DBHelper may fail.")
            self.service_client = None
        else:
            self.service_client = TableServiceClient.from_connection_string(conn_str)

    def _get_table_client(self, table):
        if not self.service_client:
            raise ConnectionError("Azure Storage Connection String not configured.")
        
        # Use sanitized table name if mapped
        azure_table_name = self.table_name_map.get(table, table)
        table_client = self.service_client.get_table_client(azure_table_name)
        try:
            table_client.create_table()
        except:
            pass # Already exists
        return table_client

    def extract(self, table, fields=None, conditions=None):
        """Extracts data from Azure Table Storage and returns a DataFrame."""
        table_client = self._get_table_client(table)
        pk_val, rk_col = self.key_map.get(table, ("DATA", "id"))
        
        query = ""
        if pk_val:
            query = f"PartitionKey eq '{pk_val}'"
        
        if conditions:
            for key, value in conditions.items():
                # Map original ID name to RowKey if applicable
                filter_key = "RowKey" if key == rk_col else key
                # Sanitize value if it's used as a key in the filter
                sanitized_value = sanitize_key(value) if filter_key in ["PartitionKey", "RowKey"] else value
                
                # Simple OData filter builder
                clause = f"{filter_key} eq '{sanitized_value}'" if isinstance(sanitized_value, str) else f"{filter_key} eq {value}"
                query = f"({query}) and ({clause})" if query else clause

        try:
            entities = table_client.query_entities(query_filter=query) if query else table_client.list_entities()
            df = pd.DataFrame(list(entities))
        except Exception as e:
            logging.error(f"Error extracting from {table}: {e}")
            return pd.DataFrame()

        if df.empty:
            return pd.DataFrame()

        # Aliasing: Restore original ID column from RowKey
        if rk_col in self.key_map.get(table, (None, None))[1:] or rk_col == self.key_map.get(table, (None, "id"))[1]:
            df[rk_col] = df["RowKey"]
        
        # Cleanup Azure internal columns for clean DataFrame
        cols_to_drop = ["PartitionKey", "RowKey", "Timestamp", "etag"]
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

        if fields:
            # Ensure requested fields exist (might be aliased or original)
            existing_fields = [f for f in fields if f in df.columns]
            df = df[existing_fields]

        return df

    def load(self, table, dataframe, mode='append'):
        """Loads data into Azure Table using Upsert logic."""
        table_client = self._get_table_client(table)
        pk_val, rk_col = self.key_map.get(table, ("DATA", "id"))

        for _, row in dataframe.iterrows():
            entity = row.to_dict()
            
            # Set PartitionKey
            if pk_val:
                entity["PartitionKey"] = pk_val
            elif "doc_id" in entity: # Special case for bridge
                entity["PartitionKey"] = sanitize_key(entity["doc_id"])
            else:
                entity["PartitionKey"] = "DATA"

            # Set RowKey
            if rk_col in entity:
                entity["RowKey"] = sanitize_key(entity[rk_col])
            else:
                import uuid
                entity["RowKey"] = str(uuid.uuid4())

            # Handle NaN/Null and Large Integers for Azure
            for k, v in entity.items():
                if pd.isna(v):
                    entity[k] = None
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    # Handle INT32 overflow
                    if (isinstance(v, int) or (isinstance(v, float) and v.is_integer())) and \
                       (v > 2147483647 or v < -2147483648):
                        entity[k] = str(int(v))
                    else:
                        entity[k] = v

            table_client.upsert_entity(entity)

    def modify(self, table, update_values, conditions):
        """Queries entities, modifies them in DataFrame, and upserts back."""
        df = self.extract(table, conditions=conditions)
        if df.empty: return

        # Apply updates
        for col, val in update_values.items():
            df[col] = val
            
        if 'last_modified_at' in df.columns:
            df['last_modified_at'] = get_now()

        self.load(table, df)

    def delete(self, table, conditions):
        """Deletes entities matching conditions."""
        table_client = self._get_table_client(table)
        # Extract to get PK and RK of targets
        df = self.extract(table, conditions=conditions)
        if df.empty: return

        pk_val, rk_col = self.key_map.get(table, ("DATA", "id"))
        
        for _, row in df.iterrows():
            # Original ID might have been sanitized when stored as RowKey
            rk = sanitize_key(row[rk_col])
            pk = pk_val if pk_val else sanitize_key(row["doc_id"])
            try:
                table_client.delete_entity(partition_key=pk, row_key=rk)
            except ResourceNotFoundError:
                pass

    def upsert(self, table, new_df, id_col):
        """Implementation remains similar but redirected to load which uses upsert_entity."""
        self.load(table, new_df)
