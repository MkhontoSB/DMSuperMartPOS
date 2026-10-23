
import pytest
import csv
import io
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


def test_admin_can_create_product_with_zero_initial_stock(api_context):
    response = api_context.post(
        "/api/v1/inventory",
        headers=auth_headers(1),
        json={
            "item_id": "000987",
            "barcode": "6001234567891",
            "name": "New Product",
            "product_category": "Household",
            "cost_price": "12.50",
            "selling_price": "18.99",
            "low_stock_threshold": 4,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["item_id"] == "000987"
    assert response.json()["quantity"] == 0
    assert response.json()["selling_price"] == "18.99"


def test_non_admin_cannot_create_product(api_context):
    response = api_context.post(
        "/api/v1/inventory",
        headers=auth_headers(2),
        json={"item_id": "new-1", "name": "New Product"},
    )
    assert response.status_code == 403


def test_duplicate_item_id_is_rejected(api_context):
    response = api_context.post(
        "/api/v1/inventory",
        headers=auth_headers(1),
        json={"item_id": "000123", "name": "Duplicate Product"},
    )
    assert response.status_code == 409


def test_admin_can_read_product_by_item_id(api_context):
    response = api_context.get(
        "/api/v1/inventory/000123",
        headers=auth_headers(1),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Test Product"
    assert response.json()["item_id"] == "000123"


def test_admin_can_update_product_metadata(api_context):
    response = api_context.patch(
        "/api/v1/inventory/000123",
        headers=auth_headers(1),
        json={"name": "Updated Product", "selling_price": "17.50"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Updated Product"
    assert response.json()["selling_price"] == "17.50"
    assert response.json()["quantity"] == 25


def test_product_update_rejects_negative_price(api_context):
    response = api_context.patch(
        "/api/v1/inventory/000123",
        headers=auth_headers(1),
        json={"selling_price": "-1.00"},
    )
    assert response.status_code == 422


def test_product_cannot_be_deleted_while_stock_remains(api_context):
    response = api_context.delete(
        "/api/v1/inventory/000123",
        headers=auth_headers(1),
    )
    assert response.status_code == 409


def test_non_admin_cannot_update_product(api_context):
    response = api_context.patch(
        "/api/v1/inventory/000123",
        headers=auth_headers(2),
        json={"name": "Unauthorized Change"},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/inventory/low-stock", None),
        ("get", "/api/v1/inventory/export.csv", None),
        (
            "post",
            "/api/v1/inventory/barcodes/pdf",
            {"item_ids": ["000123"], "barcode_type": "Code 39"},
        ),
    ],
)
def test_inventory_feature_endpoints_require_authentication(
    api_context, method, path, payload
):
    response = getattr(api_context, method)(
        path,
        json=payload,
    ) if payload is not None else getattr(api_context, method)(path)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/inventory/low-stock", None),
        ("get", "/api/v1/inventory/export.csv", None),
        (
            "post",
            "/api/v1/inventory/barcodes/pdf",
            {"item_ids": ["000123"], "barcode_type": "Code 39"},
        ),
    ],
)
def test_store_owner_cannot_access_inventory_feature_endpoints(
    api_context, method, path, payload
):
    response = getattr(api_context, method)(
        path,
        headers=auth_headers(2),
        json=payload,
    ) if payload is not None else getattr(api_context, method)(
        path,
        headers=auth_headers(2),
    )

    assert response.status_code == 403


def test_admin_can_read_low_stock_products(api_context):
    create_response = api_context.post(
        "/api/v1/inventory",
        headers=auth_headers(1),
        json={
            "item_id": "000124",
            "name": "Low Stock Product",
            "low_stock_threshold": 5,
        },
    )
    assert create_response.status_code == 201, create_response.text

    response = api_context.get(
        "/api/v1/inventory/low-stock",
        headers=auth_headers(1),
    )

    assert response.status_code == 200, response.text
    products = response.json()
    assert any(
        product["item_id"] == "000124"
        and product["quantity"] < product["low_stock_threshold"]
        for product in products
    )
    assert all(
        product["quantity"] < product["low_stock_threshold"]
        for product in products
    )


def test_admin_can_export_inventory_csv(api_context):
    response = api_context.get(
        "/api/v1/inventory/export.csv",
        headers=auth_headers(1),
    )

    assert response.status_code == 200, response.text
    assert "text/csv" in response.headers["content-type"]
    assert 'attachment; filename="warehouse.csv"' in response.headers[
        "content-disposition"
    ]

    content = response.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(content)))

    assert rows
    product = next(row for row in rows if row["item_id"] == "000123")
    assert product["name"] == "Test Product"
    assert product["quantity"] == "25"
    assert product["selling_price"] == "15.00"


def test_admin_can_generate_code39_barcode_pdf(api_context):
    response = api_context.post(
        "/api/v1/inventory/barcodes/pdf",
        headers=auth_headers(1),
        json={
            "item_ids": ["000123"],
            "barcode_type": "Code 39",
            "copies_per_item": 1,
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="supermart_barcodes.pdf"' in response.headers[
        "content-disposition"
    ]
    assert response.content.startswith(b"%PDF")


def test_barcode_pdf_rejects_unknown_product(api_context):
    response = api_context.post(
        "/api/v1/inventory/barcodes/pdf",
        headers=auth_headers(1),
        json={
            "item_ids": ["missing-product"],
            "barcode_type": "Code 39",
        },
    )

    assert response.status_code == 404


def test_barcode_pdf_rejects_invalid_ean13(api_context):
    response = api_context.post(
        "/api/v1/inventory/barcodes/pdf",
        headers=auth_headers(1),
        json={
            "item_ids": ["000123"],
            "barcode_type": "EAN-13",
        },
    )

    assert response.status_code == 422
