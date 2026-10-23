from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from supermart.api.dependencies import get_current_user
from supermart.api.schemas import (
    InventoryItemRead,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from supermart.database import get_db
from supermart.models import User
from supermart.services.inventory_service import (
    create_warehouse_product,
    delete_warehouse_product,
    get_product_details,
    get_warehouse_inventory,
    update_warehouse_product,
)

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])


@router.get("", response_model=list[InventoryItemRead])
def read_warehouse_inventory(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InventoryItemRead]:
    """Retrieve warehouse inventory for system administrators."""
    return get_warehouse_inventory(db, current_user)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product_endpoint(
    payload: ProductCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductRead:
    """Create product metadata. New products start with zero warehouse stock."""
    return create_warehouse_product(db, current_user, payload)


@router.get("/{item_id}", response_model=ProductRead)
def read_product_endpoint(
    item_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductRead:
    return get_product_details(db, current_user, item_id)


@router.patch("/{item_id}", response_model=ProductRead)
def update_product_endpoint(
    item_id: str,
    payload: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProductRead:
    """Update product metadata without bypassing the stock movement ledger."""
    return update_warehouse_product(db, current_user, item_id, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_endpoint(
    item_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    delete_warehouse_product(db, current_user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
