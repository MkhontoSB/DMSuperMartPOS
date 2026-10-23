from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from supermart.api.schemas import ProductCreate, ProductUpdate
from supermart.models import AuditEvent, User, WarehouseStock
from supermart.repositories.product_repository import (
    create_product,
    delete_product,
    get_product,
    get_product_by_barcode,
    list_products,
    product_has_history_or_store_stock,
    supplier_exists,
)
from supermart.repositories.stock_repository import list_warehouse_inventory
from supermart.security.authorization import require_role
from supermart.security.roles import Role


def _require_inventory_admin(current_user: User) -> None:
    require_role(current_user, {Role.SYSTEM_ADMIN.value})


def _audit(db: Session, user: User, action: str, item_id: str, details: str) -> None:
    db.add(AuditEvent(
        actor_user_id=user.user_id,
        action=action,
        resource_type="warehouse_product",
        resource_id=item_id,
        details=details,
        outcome="success",
    ))


def _validate_supplier(db: Session, supplier_id: int | None) -> None:
    if supplier_id is not None and not supplier_exists(db, supplier_id):
        raise HTTPException(status_code=422, detail="Supplier does not exist.")


def get_warehouse_inventory(
    db: Session,
    current_user: User,
) -> list[WarehouseStock]:
    """Return warehouse inventory to authorised administrators."""
    _require_inventory_admin(current_user)
    return list_warehouse_inventory(db)


def get_product_details(db: Session, current_user: User, item_id: str) -> WarehouseStock:
    _require_inventory_admin(current_user)
    product = get_product(db, item_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product


def create_warehouse_product(
    db: Session, current_user: User, payload: ProductCreate
) -> WarehouseStock:
    _require_inventory_admin(current_user)
    item_id = payload.item_id.strip()
    if get_product(db, item_id) is not None:
        raise HTTPException(status_code=409, detail="Item ID already exists.")
    if payload.barcode and get_product_by_barcode(db, payload.barcode) is not None:
        raise HTTPException(status_code=409, detail="Barcode is already assigned to another product.")
    _validate_supplier(db, payload.supplier_id)

    product = WarehouseStock(
        item_id=item_id,
        barcode=payload.barcode,
        name=payload.name,
        product_category=payload.product_category,
        quantity=0,
        cost_price=payload.cost_price,
        selling_price=payload.selling_price,
        supplier_id=payload.supplier_id,
        low_stock_threshold=payload.low_stock_threshold,
        expiry_date=payload.expiry_date,
    )
    try:
        create_product(db, product)
        _audit(db, current_user, "inventory.product.create", item_id, "Product created; initial warehouse quantity set to zero.")
        db.commit()
        db.refresh(product)
        return product
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Product conflicts with an existing record or database constraint.") from exc
    except Exception:
        db.rollback()
        raise


def update_warehouse_product(
    db: Session, current_user: User, item_id: str, payload: ProductUpdate
) -> WarehouseStock:
    _require_inventory_admin(current_user)
    product = get_product(db, item_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one product field must be supplied.")
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status_code=422, detail="Product name cannot be null.")
    if "low_stock_threshold" in changes and changes["low_stock_threshold"] is None:
        raise HTTPException(status_code=422, detail="Low-stock threshold cannot be null.")
    if "cost_price" in changes and changes["cost_price"] is None:
        raise HTTPException(status_code=422, detail="Cost price cannot be null.")
    if "selling_price" in changes and changes["selling_price"] is None:
        raise HTTPException(status_code=422, detail="Selling price cannot be null.")
    if "supplier_id" in changes:
        _validate_supplier(db, changes["supplier_id"])
    if changes.get("barcode") and changes["barcode"] != product.barcode:
        existing = get_product_by_barcode(db, changes["barcode"])
        if existing is not None and existing.item_id != item_id:
            raise HTTPException(status_code=409, detail="Barcode is already assigned to another product.")

    try:
        for field, value in changes.items():
            setattr(product, field, value)
        _audit(db, current_user, "inventory.product.update", item_id, "Updated fields: " + ", ".join(sorted(changes)))
        db.commit()
        db.refresh(product)
        return product
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Product update conflicts with a database constraint.") from exc
    except Exception:
        db.rollback()
        raise


def delete_warehouse_product(db: Session, current_user: User, item_id: str) -> None:
    _require_inventory_admin(current_user)
    product = get_product(db, item_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    if (product.quantity or 0) != 0:
        raise HTTPException(status_code=409, detail="Product cannot be deleted while warehouse stock remains.")
    if product_has_history_or_store_stock(db, item_id):
        raise HTTPException(status_code=409, detail="Product cannot be deleted because stock, barcode, or transaction history references it.")
    try:
        _audit(db, current_user, "inventory.product.delete", item_id, "Product deleted.")
        delete_product(db, product)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Product is referenced by another record and cannot be deleted.") from exc
    except Exception:
        db.rollback()
        raise
