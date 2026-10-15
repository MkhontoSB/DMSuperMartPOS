# supplier_account_service.py
from argon2 import PasswordHasher
from sqlalchemy import select

from supermart.models import (
    User,
    Supplier,
    SupplierUserLink,
    AuditLog,
)

password_hasher = PasswordHasher()


def create_supplier_account(
    db,
    admin,
    username,
    supplier_id,
    initial_password,
):
    # 1. Authorize the administrator.
    if admin is None or admin.get("role") != "system_admin":
        raise PermissionError(
            "Only a system administrator can create supplier accounts"
        )

    username = username.strip()

    if not username:
        raise ValueError("Username is required")

    # 2. Check that the supplier company exists.
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.supplier_id == supplier_id
        )
    )

    if supplier is None:
        raise ValueError("Supplier company does not exist")

    # 3. Hash the initial credential.
    password_hash = password_hasher.hash(initial_password)

    try:
        # 4. Create an inactive supplier login.
        user = User(
            username=username,
            password=password_hash,
            role="supplier",
            is_active=False,
            must_reset_password=True,
        )
        db.add(user)
        db.flush()

        # 5. Link the login to the selected company.
        link = SupplierUserLink(
            user_id=user.user_id,
            supplier_id=supplier.supplier_id,
        )
        db.add(link)

        # 6. Record the administrative action.
        audit = AuditLog(
            actor_user_id=admin["id"],
            action="SUPPLIER_ACCOUNT_CREATED",
            target_user_id=user.user_id,
            details=f"Supplier ID: {supplier.supplier_id}",
        )
        db.add(audit)

        # 7. Commit all changes together.
        db.commit()

        return user.user_id

    except Exception:
        db.rollback()
        raise
