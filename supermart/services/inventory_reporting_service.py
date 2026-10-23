"""Read-only inventory reporting and CSV export operations."""
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from supermart.models import User, WarehouseStock
from supermart.security.authorization import require_role
from supermart.security.roles import Role


def _require_inventory_admin(user: User) -> None:
    require_role(user, {Role.SYSTEM_ADMIN.value})


def list_low_stock(db: Session, user: User) -> list[WarehouseStock]:
    """Products whose quantity is below their configured threshold."""
    _require_inventory_admin(user)
    return list(db.scalars(
        select(WarehouseStock)
        .where(WarehouseStock.quantity < WarehouseStock.low_stock_threshold)
        .order_by(WarehouseStock.name, WarehouseStock.item_id)
    ).all())


def export_inventory_csv(db: Session, user: User) -> bytes:
    """Export product metadata and current quantity for authorised admin use."""
    _require_inventory_admin(user)
    products = db.scalars(select(WarehouseStock).order_by(WarehouseStock.item_id)).all()
    output = io.StringIO(newline="")
    fields = [
        "item_id", "barcode", "name", "country_gs1", "manufacturer_code", "product_code",
        "product_category", "quantity", "cost_price", "selling_price", "supplier_id",
        "low_stock_threshold", "expiry_date",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for product in products:
        writer.writerow({
            "item_id": product.item_id,
            "barcode": product.barcode or "",
            "name": product.name or "",
            "country_gs1": getattr(product, "country_gs1", None) or "",
            "manufacturer_code": product.manufacturer_code or "",
            "product_code": product.product_code or "",
            "product_category": product.product_category or "",
            "quantity": product.quantity if product.quantity is not None else 0,
            "cost_price": product.cost_price if product.cost_price is not None else Decimal("0.00"),
            "selling_price": product.selling_price if product.selling_price is not None else Decimal("0.00"),
            "supplier_id": product.supplier_id or "",
            "low_stock_threshold": product.low_stock_threshold if product.low_stock_threshold is not None else 5,
            "expiry_date": product.expiry_date.isoformat() if isinstance(product.expiry_date, date) else (product.expiry_date or ""),
        })
    return output.getvalue().encode("utf-8-sig")
