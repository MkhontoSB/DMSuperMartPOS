# supermart/services/stock_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from supermart.models import Store
from supermart.repositories.stock_repository import apply_stock_transfer
from supermart.security.authorization import (
    require_role,
    require_store_access,
)
from supermart.security.roles import Role


def transfer_stock(
    db: Session,
    item_id: str,
    qty: int,
    store_id: int,
    current_user,
) -> bool:
    """Authorize and execute a warehouse-to-store stock transfer."""

    try:
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        require_role(
            current_user,
            {
                Role.SYSTEM_ADMIN.value,
                Role.STORE_OWNER.value,
            },
        )

        if not isinstance(item_id, str) or not item_id.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid item ID is required.")
            

        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transfer quantity must be a positive integer.")
                

        if isinstance(store_id, bool) or not isinstance(store_id, int) or store_id <= 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="A valid store ID is required.")

        # Enforce store ownership before accessing its stock.
        require_store_access(db, current_user, store_id)

        store = db.get(Store, store_id)

        if store is None or not store.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="The destination store is unavailable.")

        transferred = apply_stock_transfer(
            db=db,
            item_id=item_id.strip(),
            qty=qty,
            store_id=store_id,
            actor_user_id=current_user.user_id,
        )

        if not transferred:
            db.rollback()
            return False

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise
