# supermart/api/schemas.py
from pydantic import BaseModel, ConfigDict


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    barcode: str | None
    name: str
    product_category: str | None
    quantity: int
