
import pytest

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from supermart.models import (
    Base,
    User,
    Store,
    StoreMembership,
    Supplier,
    SupplierUserLink,
)
from supermart.security.authorization import (
    require_store_access,
    require_supplier_link,
)
from supermart.security.roles import Role


@pytest.fixture
def db():
    """Create an isolated database for each integration test."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def records(db):
    """Insert actual users, stores, and suppliers."""
    admin = User(
        user_id=1,
        username="admin_test",
        password_hash="test-hash",
        role=Role.SYSTEM_ADMIN.value,
    )
    owner = User(
        user_id=2,
        username="owner_test",
        password_hash="test-hash",
        role=Role.STORE_OWNER.value,
    )
    supplier_user = User(
        user_id=3,
        username="supplier_test",
        password_hash="test-hash",
        role=Role.SUPPLIER.value,
    )
    other_supplier_user = User(
        user_id=4,
        username="other_supplier_test",
        password_hash="test-hash",
        role=Role.SUPPLIER.value,
    )

    store_a = Store(store_id=10, name="Store A")
    store_b = Store(store_id=20, name="Store B")

    supplier_a = Supplier(supplier_id=100, name="Supplier A")
    supplier_b = Supplier(supplier_id=200, name="Supplier B")

    db.add_all([
        admin,
        owner,
        supplier_user,
        other_supplier_user,
        store_a,
        store_b,
        supplier_a,
        supplier_b,
    ])
    db.flush()

    db.add_all([
        StoreMembership(user_id=2, store_id=10),
        SupplierUserLink(user_id=3, supplier_id=100),
        SupplierUserLink(user_id=4, supplier_id=200),
    ])
    db.commit()

    return {
        "admin": admin,
        "owner": owner,
        "supplier_user": supplier_user,
        "other_supplier_user": other_supplier_user,
        "store_a": store_a,
        "store_b": store_b,
        "supplier_a": supplier_a,
        "supplier_b": supplier_b,
    }


# --------------------------------------------------
# Store authorization integration tests
# --------------------------------------------------

def test_owner_can_access_store_with_real_membership(db, records):
    require_store_access(db, records["owner"], store_id=10)


def test_owner_cannot_access_store_without_membership(db, records):
    with pytest.raises(HTTPException) as exc:
        require_store_access(db, records["owner"], store_id=20)

    assert exc.value.status_code == 403


def test_admin_can_access_store_without_membership(db, records):
    require_store_access(db, records["admin"], store_id=20)


def test_supplier_cannot_access_store(db, records):
    with pytest.raises(HTTPException) as exc:
        require_store_access(
            db, records["supplier_user"], store_id=10
        )

    assert exc.value.status_code == 403


# --------------------------------------------------
# Supplier authorization integration tests
# --------------------------------------------------

def test_supplier_can_access_own_linked_supplier(db, records):
    require_supplier_link(
        db, records["supplier_user"], supplier_id=100
    )


def test_supplier_cannot_access_another_supplier(db, records):
    with pytest.raises(HTTPException) as exc:
        require_supplier_link(
            db, records["supplier_user"], supplier_id=200
        )

    assert exc.value.status_code == 403


def test_second_supplier_can_access_own_supplier(db, records):
    require_supplier_link(
        db, records["other_supplier_user"], supplier_id=200
    )


def test_store_owner_cannot_access_supplier_records(db, records):
    with pytest.raises(HTTPException) as exc:
        require_supplier_link(
            db, records["owner"], supplier_id=100
        )

    assert exc.value.status_code == 403
