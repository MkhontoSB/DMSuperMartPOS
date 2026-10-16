# supermart/api/stock_repository.py

from sqlalchemy import select
from sqlalchemy.orm import Session

from supermart.models import (
    AuditEvent,
    StockMovement,
    StoreStock,
    WarehouseStock,
)


def get_warehouse_quantity(db: Session, item_id: str) -> int | None:
    """Return the warehouse quantity for an item, or None if absent."""
    warehouse_stock = db.get(WarehouseStock, item_id)

    if warehouse_stock is None:
        return None

    return warehouse_stock.quantity


def apply_stock_transfer(
    db: Session,
    item_id: str,
    qty: int,
    store_id: int,
    actor_user_id: int,
) -> bool:
    """
    Apply a warehouse-to-store transfer.

    The caller owns the transaction and must commit on success or
    roll back on failure.
    """
    warehouse_stock = db.scalar(
        select(WarehouseStock)
        .where(WarehouseStock.item_id == item_id)
        .with_for_update()
    )

    if warehouse_stock is None or warehouse_stock.quantity < qty:
        return False

    store_stock = db.scalar(
        select(StoreStock)
        .where(
            StoreStock.store_id == store_id,
            StoreStock.item_id == item_id,
        )
        .with_for_update()
    )

    # Deduct from the warehouse.
    warehouse_stock.quantity -= qty

    # Add to the selected store, creating its stock row if necessary.
    if store_stock is None:
        store_stock = StoreStock(
            store_id=store_id,
            item_id=item_id,
            quantity=qty,
            product_category=warehouse_stock.product_category,
        )
        db.add(store_stock)
    else:
        store_stock.quantity += qty

    # Record the movement in the stock-movement ledger.
    db.add(
        StockMovement(
            item_id=item_id,
            source_location_type="warehouse",
            source_store_id=None,
            destination_location_type="store",
            destination_store_id=store_id,
            quantity=qty,
            actor_user_id=actor_user_id,
        )
    )

    # Also record the operation in the general audit log.
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action="stock.transfer",
            resource_type="stock_transfer",
            resource_id=f"{store_id}:{item_id}",
            details=(
                f"Warehouse to store {store_id}; "
                f"item {item_id}; quantity {qty}"
            ),
            outcome="success",
        )
    )

    db.flush()
    return True


def list_warehouse_inventory(db: Session) -> list[WarehouseStock]:
    """Return warehouse inventory in a consistent order."""
    statement = select(WarehouseStock).order_by(
        WarehouseStock.item_id
    )
    return list(db.scalars(statement).all())
