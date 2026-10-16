from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from supermart.api.dependencies import get_current_user
from supermart.api.schemas import InventoryItemRead
from supermart.database import get_db
from supermart.models import User
from supermart.services.inventory_service import (
    get_warehouse_inventory,
)


router = APIRouter(
    prefix="/api/v1/inventory",
    tags=["Inventory"],
)


@router.get(
    "",
    response_model=list[InventoryItemRead],
)
def read_warehouse_inventory(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[InventoryItemRead]:
    """Retrieve warehouse inventory for system administrators."""

    return get_warehouse_inventory(db, current_user)
