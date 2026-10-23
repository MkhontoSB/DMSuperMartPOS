"""Database access for warehouse product records."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from supermart.models import (
    Barcode,
    StockMovement,
    StoreStock,
    Supplier,
    Transaction,
    WarehouseStock,
)


def get_product(db: Session, item_id: str) -> WarehouseStock | None:
    return db.get(WarehouseStock, item_id)


def list_products(db: Session) -> list[WarehouseStock]:
    statement = select(WarehouseStock).order_by(WarehouseStock.item_id)
    return list(db.scalars(statement).all())


def get_product_by_barcode(db: Session, barcode: str) -> WarehouseStock | None:
    return db.scalar(
        select(WarehouseStock).where(WarehouseStock.barcode == barcode)
    )


def supplier_exists(db: Session, supplier_id: int) -> bool:
    return db.get(Supplier, supplier_id) is not None


def create_product(db: Session, product: WarehouseStock) -> WarehouseStock:
    db.add(product)
    db.flush()
    return product


def product_has_history_or_store_stock(db: Session, item_id: str) -> bool:
    """Prevent deletion when another table depends on this product."""
    reference_checks = (
        select(Barcode.item_id).where(Barcode.item_id == item_id).limit(1),
        select(StoreStock.item_id).where(StoreStock.item_id == item_id).limit(1),
        select(Transaction.item_id).where(Transaction.item_id == item_id).limit(1),
        select(StockMovement.item_id).where(StockMovement.item_id == item_id).limit(1),
    )
    return any(db.scalar(statement) is not None for statement in reference_checks)


def delete_product(db: Session, product: WarehouseStock) -> None:
    db.delete(product)
    db.flush()
