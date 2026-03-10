import os

import pandas as pd

from db.table_storage import DBHelper, sanitize_key


def _resolve_dataset_dir() -> str:
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "data", "dataset"),
        os.path.join(os.path.dirname(__file__), "..", "..", "cowhorse_v2", "api", "dataset"),
    ]
    for path in candidates:
        resolved = os.path.abspath(path)
        if os.path.exists(resolved):
            return resolved
    return os.path.abspath(candidates[0])


def run_data_loader():
    dataset_dir = _resolve_dataset_dir()
    if not os.path.exists(dataset_dir):
        raise RuntimeError(f"Dataset directory not found at {dataset_dir}")

    results: dict[str, str] = {}
    db = DBHelper()
    if not db.service_client:
        raise RuntimeError("Azure Storage Connection String not configured.")

    for filename in os.listdir(dataset_dir):
        if not filename.endswith(".csv"):
            continue

        table_name = filename.replace(".csv", "")
        csv_path = os.path.join(dataset_dir, filename)
        df = pd.read_csv(csv_path)

        pk_val, rk_col = db.key_map.get(table_name, ("DATA", "id"))
        table_client = db._get_table_client(table_name)

        rows_loaded = 0
        dedup_dict: dict[tuple[str, str], dict] = {}
        for index, row in df.iterrows():
            entity = row.to_dict()

            if pk_val:
                entity["PartitionKey"] = pk_val
            elif "doc_id" in entity:
                entity["PartitionKey"] = sanitize_key(entity["doc_id"])
            else:
                entity["PartitionKey"] = "DATA"

            if rk_col in entity and pd.notna(entity[rk_col]):
                entity["RowKey"] = sanitize_key(entity[rk_col])
            else:
                entity["RowKey"] = f"row_{index}"

            for key, val in entity.items():
                if pd.isna(val):
                    entity[key] = None
                elif isinstance(val, (int, float)) and not isinstance(val, bool):
                    if (
                        (isinstance(val, int) or (isinstance(val, float) and val.is_integer()))
                        and (val > 2147483647 or val < -2147483648)
                    ):
                        entity[key] = str(int(val))
                    else:
                        entity[key] = val

            dedup_dict[(entity["PartitionKey"], entity["RowKey"])] = entity

        for entity in dedup_dict.values():
            table_client.upsert_entity(entity=entity)
            rows_loaded += 1

        results[table_name] = f"Loaded {rows_loaded} rows."

    return {"message": "Data migration complete", "details": results}
