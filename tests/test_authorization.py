
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from supermart.security.authorization import (
    require_role,
    require_store_access,
    require_supplier_link,
)
from supermart.security.roles import Role


@pytest.fixture
def db():
    """Provide a mocked database session."""
    return MagicMock()


@pytest.fixture
def system_admin():
    return SimpleNamespace(
        user_id=1,
        role=Role.SYSTEM_ADMIN.value,
    )


@pytest.fixture
def store_owner():
    return SimpleNamespace(
        user_id=2,
        role=Role.STORE_OWNER.value,
    )


@pytest.fixture
def supplier_user():
    return SimpleNamespace(
        user_id=3,
        role=Role.SUPPLIER.value,
    )


# --------------------------------------------------
# require_role tests
# --------------------------------------------------

def test_require_role_allows_authorized_user(system_admin):
    require_role(system_admin, [Role.SYSTEM_ADMIN.value])


def test_require_role_rejects_unauthorized_user(store_owner):
    with pytest.raises(HTTPException) as exc:
        require_role(store_owner, [Role.SYSTEM_ADMIN.value])

    assert exc.value.status_code == 403


def test_require_role_rejects_missing_user():
    with pytest.raises(HTTPException) as exc:
        require_role(None, [Role.SYSTEM_ADMIN.value])

    assert exc.value.status_code == 403


# --------------------------------------------------
# require_store_access tests
# --------------------------------------------------

def test_system_admin_can_access_any_store(db, system_admin):
    require_store_access(db, system_admin, store_id=100)

    # Administrators should not need a membership lookup.
    db.scalar.assert_not_called()


def test_store_owner_can_access_linked_store(db, store_owner):
    db.scalar.return_value = store_owner.user_id

    require_store_access(db, store_owner, store_id=10)

    db.scalar.assert_called_once()


def test_store_owner_cannot_access_unlinked_store(db, store_owner):
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        require_store_access(db, store_owner, store_id=99)

    assert exc.value.status_code == 403


def test_supplier_cannot_access_store(db, supplier_user):
    with pytest.raises(HTTPException) as exc:
        require_store_access(db, supplier_user, store_id=10)

    assert exc.value.status_code == 403
    db.scalar.assert_not_called()


# --------------------------------------------------
# require_supplier_link tests
# --------------------------------------------------

def test_supplier_can_access_linked_supplier(db, supplier_user):
    db.scalar.return_value = supplier_user.user_id

    require_supplier_link(db, supplier_user, supplier_id=20)

    db.scalar.assert_called_once()


def test_supplier_cannot_access_unlinked_supplier(db, supplier_user):
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc:
        require_supplier_link(db, supplier_user, supplier_id=99)

    assert exc.value.status_code == 403


def test_store_owner_cannot_access_supplier_records(db, store_owner):
    with pytest.raises(HTTPException) as exc:
        require_supplier_link(db, store_owner, supplier_id=20)

    assert exc.value.status_code == 403
    db.scalar.assert_not_called()


def test_system_admin_cannot_use_supplier_link_check(db, system_admin):
    with pytest.raises(HTTPException) as exc:
        require_supplier_link(db, system_admin, supplier_id=20)

    assert exc.value.status_code == 403
    db.scalar.assert_not_called()


def test_missing_user_cannot_access_store(db):
    with pytest.raises(HTTPException) as exc:
        require_store_access(db, None, store_id=10)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Store access denied"
    db.scalar.assert_not_called()


def test_missing_user_cannot_access_supplier(db):
    with pytest.raises(HTTPException) as exc:
        require_supplier_link(db, None, supplier_id=20)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Supplier access denied"
    db.scalar.assert_not_called()
