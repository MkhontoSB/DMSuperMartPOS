from supermart.repositories.stock_repository import (
    apply_stock_transfer,
)


def transfer_stock(item_id, qty, current_user):
    """Validate and authorize a warehouse-to-store transfer."""

    if not current_user:
        raise PermissionError("Authentication required.")

    allowed_roles = {"store owner", "admin"}

    if current_user.get("role") not in allowed_roles:
        raise PermissionError(
            "You are not authorized to transfer stock."
        )

    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("A valid item ID is required.")

    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        raise ValueError(
            "Transfer quantity must be a positive integer."
        )

    return apply_stock_transfer(item_id.strip(), qty)