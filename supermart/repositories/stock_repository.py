# stock_repository.py

import sqlite3

from your_database_module import get_conn


def get_warehouse_quantity(item_id):
    conn = get_conn()

    try:
        row = conn.execute(
            """
            SELECT quantity
            FROM warehouse_stock
            WHERE item_id = ?
            """,
            (item_id,),
        ).fetchone()

        return row[0] if row else None
    finally:
        conn.close()


def apply_stock_transfer(item_id, qty):
    """Execute the stock movement in one transaction."""

    conn = get_conn()

    try:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            """
            SELECT quantity, Product_Category
            FROM warehouse_stock
            WHERE item_id = ?
            """,
            (item_id,),
        ).fetchone()

        if row is None or row[0] is None or row[0] < qty:
            conn.rollback()
            return False

        category = row[1]

        conn.execute(
            """
            UPDATE warehouse_stock
            SET quantity = quantity - ?
            WHERE item_id = ?
            """,
            (qty, item_id),
        )

        conn.execute(
            """
            INSERT INTO store_stock
                (item_id, Product_Category, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(item_id)
            DO UPDATE SET quantity = quantity + excluded.quantity
            """,
            (item_id, category, qty),
        )

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()