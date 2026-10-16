
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from supermart.api.dependencies import get_db
from supermart.api.main import app
from supermart.models import Base, User, WarehouseStock
from supermart.security.roles import Role
from supermart.security.tokens import create_access_token


@pytest.fixture
def api_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add_all([
            User(
                user_id=1,
                username="admin_test",
                password_hash="test-hash",
                role=Role.SYSTEM_ADMIN.value,
                is_active=True,
                must_reset_password=False,
            ),
            User(
                user_id=2,
                username="owner_test",
                password_hash="test-hash",
                role=Role.STORE_OWNER.value,
                is_active=True,
                must_reset_password=False,
            ),
            User(
                user_id=3,
                username="supplier_test",
                password_hash="test-hash",
                role=Role.SUPPLIER.value,
                is_active=True,
                must_reset_password=False,
            ),
        ])

        db.add(
            WarehouseStock(
                item_id="000123",
                barcode="6001234567890",
                name="Test Product",
                product_category="Groceries",
                quantity=25,
                cost_price=10.00,
                selling_price=15.00,
            )
        )
        db.commit()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            with TestClient(app) as client:
                yield client
        finally:
            app.dependency_overrides.pop(get_db, None)

    Base.metadata.drop_all(engine)
    engine.dispose()


def auth_headers(user_id: int) -> dict[str, str]:
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


def test_inventory_requires_authentication(api_context):
    response = api_context.get("/api/v1/inventory")

    assert response.status_code == 401


def test_store_owner_cannot_read_warehouse_inventory(api_context):
    response = api_context.get(
        "/api/v1/inventory",
        headers=auth_headers(2),
    )

    assert response.status_code == 403


def test_supplier_cannot_read_warehouse_inventory(api_context):
    response = api_context.get(
        "/api/v1/inventory",
        headers=auth_headers(3),
    )

    assert response.status_code == 403


def test_admin_can_read_warehouse_inventory(api_context):
    response = api_context.get(
        "/api/v1/inventory",
        headers=auth_headers(1),
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "item_id": "000123",
            "barcode": "6001234567890",
            "name": "Test Product",
            "product_category": "Groceries",
            "quantity": 25,
        }
    ]


def test_inventory_response_does_not_expose_prices(api_context):
    response = api_context.get(
        "/api/v1/inventory",
        headers=auth_headers(1),
    )

    assert response.status_code == 200

    item = response.json()[0]
    assert "cost_price" not in item
    assert "selling_price" not in item
