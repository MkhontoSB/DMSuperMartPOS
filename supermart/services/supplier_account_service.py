# supplier_account_service.py

from argon2 import PasswordHasher
from sqlalchemy import select

from supermart.models import (
    User,
    Supplier,
    SupplierUserLink,
    AuditEvent,
)
from supermart.security.authorization import require_role
from supermart.security.roles import Role


password_hasher = PasswordHasher()


def create_supplier_account(
    db,
    admin,
    username: str,
    supplier_id: int,
    initial_password: str,
) -> int:
    """Create an inactive supplier account and link it to a supplier."""

    # 1. Authorize the administrator.
    require_role(admin, {Role.SYSTEM_ADMIN.value})

    # 2. Validate the input.
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Username is required")

    if not isinstance(initial_password, str) or not initial_password:
        raise ValueError("Initial password is required")

    username = username.strip()

    # 3. Confirm that the supplier exists.
    supplier = db.scalar(
        select(Supplier).where(
            Supplier.supplier_id == supplier_id
        )
    )

    if supplier is None:
        raise ValueError("Supplier company does not exist")

    # 4. Reject duplicate usernames.
    existing_user = db.scalar(
        select(User.user_id).where(User.username == username)
    )

    if existing_user is not None:
        raise ValueError("Username already exists")

    # 5. Hash the initial password.
    password_hash = password_hasher.hash(initial_password)

    try:
        # 6. Create an inactive account requiring a password reset.
        user = User(
            username=username,
            password_hash=password_hash,
            role=Role.SUPPLIER.value,
            is_active=False,
            must_reset_password=True,
        )
        db.add(user)
        db.flush()

        # 7. Link the account to its supplier.
        db.add(
            SupplierUserLink(
                user_id=user.user_id,
                supplier_id=supplier.supplier_id,
            )
        )

        # 8. Record the administrative action.
        db.add(
            AuditEvent(
                actor_user_id=admin.user_id,
                action="SUPPLIER_ACCOUNT_CREATED",
                target_user_id=user.user_id,
                resource_type="supplier",
                resource_id=str(supplier.supplier_id),
                details=f"Created supplier account for {username}",
                outcome="success",
            )
        )

        # 9. Commit the account, link and audit event together.
        db.commit()

        return user.user_id

    except Exception:
        db.rollback()
        raise
