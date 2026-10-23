"""Additional inventory reporting, CSV export and barcode-label endpoints."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from supermart.api.dependencies import get_current_user
from supermart.database import get_db
from supermart.models import User, WarehouseStock
from supermart.services.barcode_service import generate_barcode_pdf
from supermart.services.inventory_reporting_service import export_inventory_csv, list_low_stock

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])


class BarcodePdfRequest(BaseModel):
    item_ids: list[str] = Field(min_length=1, max_length=100)
    barcode_type: Literal["EAN-13", "Code 39"] = "EAN-13"
    copies_per_item: int = Field(default=1, ge=1, le=100)


@router.get("/low-stock")
def read_low_stock(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    products = list_low_stock(db, current_user)
    return [{
        "item_id": p.item_id,
        "barcode": p.barcode,
        "name": p.name,
        "product_category": p.product_category,
        "quantity": p.quantity,
        "low_stock_threshold": p.low_stock_threshold,
    } for p in products]


@router.get("/export.csv")
def download_inventory_csv(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    content = export_inventory_csv(db, current_user)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="warehouse.csv"'},
    )


@router.post("/barcodes/pdf")
def download_barcode_pdf(
    payload: BarcodePdfRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    # Authorization is checked before looking up requested product IDs.
    from supermart.security.authorization import require_role
    from supermart.security.roles import Role
    require_role(current_user, {Role.SYSTEM_ADMIN.value})

    unique_ids = list(dict.fromkeys(value.strip() for value in payload.item_ids if value.strip()))
    if not unique_ids:
        raise HTTPException(status_code=422, detail="At least one non-empty item ID is required.")
    found = db.scalars(select(WarehouseStock).where(WarehouseStock.item_id.in_(unique_ids))).all()
    by_id = {product.item_id: product for product in found}
    missing = [item_id for item_id in unique_ids if item_id not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail={"message": "Some products were not found.", "item_ids": missing})
    try:
        pdf = generate_barcode_pdf([
            {"item_id": p.item_id, "barcode": p.barcode, "name": p.name, "selling_price": p.selling_price}
            for p in (by_id[item_id] for item_id in unique_ids)
        ], payload.barcode_type, payload.copies_per_item)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="supermart_barcodes.pdf"'},
    )
