from pydantic import BaseModel


class UpdateInventoryRequest(BaseModel):
    incoming_csv_path: str