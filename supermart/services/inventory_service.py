from sqlalchemy.orm import Session

from supermart.models import User, WarehouseStock
from supermart.repositories.stock_repository import (
    list_warehouse_inventory,
)
from supermart.security.authorization import require_role
from supermart.security.roles import Role


def get_warehouse_inventory(
    db: Session,
    current_user: User,
) -> list[WarehouseStock]:
    """Return warehouse inventory to authorised administrators."""

    require_role(
        current_user,
        {Role.SYSTEM_ADMIN.value},
    )

    return list_warehouse_inventory(db)
