# authorization.py
from fastapi import HTTPException, status
from sqlalchemy import select
from supermart.security.roles import Role
from supermart.models import StoreMembership, SupplierUserLink
 
def require_role(user, allowed_roles):
    if user is None or user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not authorised for this operation")
 

def require_store_access(db, user, store_id: int) -> None:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Store access denied",
        )

    if user.role == Role.SYSTEM_ADMIN.value:
        return

    if user.role != Role.STORE_OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Store access denied",
        )

    linked = db.scalar(
        select(StoreMembership.user_id).where(
            StoreMembership.user_id == user.user_id,
            StoreMembership.store_id == store_id,
        )
    )

    if linked is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Store access denied",
        )


def require_supplier_link(db, user, supplier_id: int) -> None:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier access denied",
        )

    if user.role != Role.SUPPLIER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier access denied",
        )

    linked = db.scalar(
        select(SupplierUserLink.user_id).where(
            SupplierUserLink.user_id == user.user_id,
            SupplierUserLink.supplier_id == supplier_id,
        )
    )

    if linked is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supplier access denied",
        )
