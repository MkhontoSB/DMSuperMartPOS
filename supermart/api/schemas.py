from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    barcode: str | None
    name: str | None
    product_category: str | None
    quantity: int | None


class ProductCreate(BaseModel):
    """Product metadata for a new warehouse item; initial stock is always zero."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=200)
    barcode: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    product_category: str | None = Field(default=None, max_length=120)
    cost_price: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    selling_price: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)
    supplier_id: int | None = Field(default=None, gt=0)
    low_stock_threshold: int = Field(default=5, ge=0)
    expiry_date: date | None = None

    @field_validator("item_id", "name", mode="before")
    @classmethod
    def strip_required_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("barcode", "product_category", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip() or None
        return value


class ProductUpdate(BaseModel):
    """Partial update of product metadata. Stock changes use stock operations."""

    model_config = ConfigDict(extra="forbid")

    barcode: str | None = Field(default=None, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    product_category: str | None = Field(default=None, max_length=120)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    selling_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    supplier_id: int | None = Field(default=None, gt=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    expiry_date: date | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("barcode", "product_category", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip() or None
        return value


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    barcode: str | None
    name: str | None
    product_category: str | None
    quantity: int | None
    cost_price: Decimal | None
    selling_price: Decimal | None
    supplier_id: int | None
    low_stock_threshold: int | None
    expiry_date: date | None
