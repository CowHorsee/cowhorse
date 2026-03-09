import logging
import json
import os
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter(prefix="/api/data-loader", tags=["Maintenance"])

from sharedlib.db_helper.db_ops import DBHelper, sanitize_key

@router.post("/run")
def run_data_loader():
    logging.info("Starting data loading process with batching and DBHelper logic.")
    
    dataset_dir = os.path.join(os.path.dirname(__file__), 'dataset')
    if not os.path.exists(dataset_dir):
        return PlainTextResponse(f"Dataset directory not found at {dataset_dir}", status_code=500)

    results = {}
    try:
        db = DBHelper()
        if not db.service_client:
            return PlainTextResponse("Azure Storage Connection String not configured.", status_code=500)

        for filename in os.listdir(dataset_dir):
            if filename.endswith(".csv"):
                table_name = filename.replace(".csv", "")
                csv_path = os.path.join(dataset_dir, filename)
                
                df = pd.read_csv(csv_path)
                
                # Use DBHelper mapping for PK and RK
                pk_val, rk_col = db.key_map.get(table_name, ("DATA", "id"))
                
                table_client = db._get_table_client(table_name)
                
                rows_loaded = 0
                dedup_dict = {} # Keyed by (PartitionKey, RowKey) to ensure unique entities
                
                for index, row in df.iterrows():
                    entity = row.to_dict()
                    
                    # 1. Set PartitionKey (aligned with db_ops.load)
                    if pk_val:
                        entity["PartitionKey"] = pk_val
                    elif "doc_id" in entity: # Special case for bridge
                        entity["PartitionKey"] = sanitize_key(entity["doc_id"])
                    else:
                        entity["PartitionKey"] = "DATA"

                    # 2. Set RowKey (aligned with db_ops.load)
                    if rk_col in entity and pd.notna(entity[rk_col]):
                        entity["RowKey"] = sanitize_key(entity[rk_col])
                    else:
                        entity["RowKey"] = f"row_{index}"
                    
                    # 3. Handle Types & Overflows
                    for key, val in entity.items():
                        if pd.isna(val):
                            entity[key] = None
                        elif isinstance(val, (int, float)) and not isinstance(val, bool):
                            if (isinstance(val, int) or (isinstance(val, float) and val.is_integer())) and \
                               (val > 2147483647 or val < -2147483648):
                                entity[key] = str(int(val))
                            else:
                                entity[key] = val

                    # Deduplicate: Maintain only the latest version of an entity (PK+RK)
                    dedup_dict[(entity["PartitionKey"], entity["RowKey"])] = entity
                
                # 4. Upload entities individually to handle dynamic PartitionKeys safely
                for entity in dedup_dict.values():
                    table_client.upsert_entity(entity=entity)
                    rows_loaded += 1
                
                results[table_name] = f"Loaded {rows_loaded} rows."

        return JSONResponse(json.loads(json.dumps({"message": "Data migration complete", "details": results})), status_code=200)

    except Exception as exc:
        logging.error(f"Error during data loading: {str(exc)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(exc)}") from exc
