# supermart/models.py

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from supermart.security.roles import Role


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


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

    __table_args__ = (
        UniqueConstraint(
            "user_id", "store_id", name="uq_store_membership_user_store"
        ),
    )

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


class WarehouseStock(Base):
    __tablename__ = "warehouse_stock"

    item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_category: Mapped[Optional[str]] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cost_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    selling_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))


class StoreStock(Base):
    __tablename__ = "store_stock"

    __table_args__ = (
        CheckConstraint(
            "quantity >= 0", name="ck_store_stock_nonnegative"
        ),
    )

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
        Integer, nullable=False, default=0
    )
    product_category: Mapped[Optional[str]] = mapped_column(String(120))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
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
        CheckConstraint("quantity > 0", name="ck_stock_movement_positive_qty"),
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
