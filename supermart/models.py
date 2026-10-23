# supermart/models.py

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from supermart.security.roles import Role


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('system_admin', 'store_owner', 'supplier')",
            name="ck_users_role_allowed",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    username: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    must_reset_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class UserSession(Base):
    """Legacy session records; importing them does not activate sessions."""

    __tablename__ = "user_sessions"

    session_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        Text, unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )


class Store(Base):
    __tablename__ = "stores"

    store_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class StoreMembership(Base):
    __tablename__ = "store_memberships"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stores.store_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False
    )
    contact_person: Mapped[Optional[str]] = mapped_column(String(150))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(254))
    address: Mapped[Optional[str]] = mapped_column(Text)


class SupplierUserLink(Base):
    __tablename__ = "supplier_user_links"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    supplier_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.supplier_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(30), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(254))
    loyalty_points: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, server_default="0"
    )


class WarehouseStock(Base):
    __tablename__ = "warehouse_stock"

    item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(100))

    # Legacy GS1 fields retained for migration compatibility.
    country_gs1: Mapped[Optional[int]] = mapped_column(
        "Country_GS1", Integer
    )
    manufacturer_code: Mapped[Optional[int]] = mapped_column(Integer)
    product_code: Mapped[Optional[int]] = mapped_column(Integer)

    name: Mapped[Optional[str]] = mapped_column(String(200))
    product_category: Mapped[Optional[str]] = mapped_column(
        "Product_Category", String(120)
    )
    quantity: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0, server_default="0"
    )
    cost_price: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2), default=0, server_default="0"
    )
    selling_price: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2), default=0, server_default="0"
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.supplier_id", ondelete="RESTRICT"),
    )
    low_stock_threshold: Mapped[Optional[int]] = mapped_column(
        Integer, default=5, server_default="5"
    )
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)


class StoreStock(Base):
    __tablename__ = "store_stock"

    __table_args__ = (
        CheckConstraint(
            "quantity >= 0", name="ck_store_stock_nonnegative"
        ),
    )

    # The target supports multiple stores. Legacy rows have no store_id,
    # so their destination store must be resolved before importing rows.
    store_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("stores.store_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    item_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("warehouse_stock.item_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    product_category: Mapped[Optional[str]] = mapped_column(
        "Product_Category", String(120)
    )


class Barcode(Base):
    __tablename__ = "Barcode"

    # PostgreSQL requires a primary-key value. The legacy NULL item_id
    # record must be excluded from normal import and investigated separately.
    item_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("warehouse_stock.item_id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    last_scanned: Mapped[Optional[str]] = mapped_column(Text)
    quantity: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, server_default="0"
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    po_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    po_number: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True
    )
    supplier_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("suppliers.supplier_id", ondelete="RESTRICT"),
    )
    status: Mapped[Optional[str]] = mapped_column(
        String(50), default="Pending", server_default="Pending"
    )
    date_created: Mapped[Optional[str]] = mapped_column(Text)
    items_json: Mapped[Optional[str]] = mapped_column(Text)
    total_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))


class Transaction(Base):
    __tablename__ = "transactions"

    trans_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    transaction_type: Mapped[Optional[str]] = mapped_column(
        "type", String(50)
    )
    item_id: Mapped[Optional[str]] = mapped_column(
        Text,
        ForeignKey("warehouse_stock.item_id", ondelete="RESTRICT"),
    )
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    discount_applied: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2)
    )
    transaction_date: Mapped[Optional[str]] = mapped_column("date", Text)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("customers.customer_id", ondelete="SET NULL"),
    )
    receipt_ref: Mapped[Optional[str]] = mapped_column(String(150))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
    )
    resource_type: Mapped[Optional[str]] = mapped_column(String(100))
    resource_id: Mapped[Optional[str]] = mapped_column(String(120))
    details: Mapped[Optional[str]] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(
        String(30), nullable=False, default="success"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0", name="ck_stock_movement_positive_qty"
        ),
    )

    movement_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    item_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("warehouse_stock.item_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_location_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    source_store_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("stores.store_id", ondelete="RESTRICT"),
    )
    destination_location_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    destination_store_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("stores.store_id", ondelete="RESTRICT"),
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
