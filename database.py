from datetime import datetime
from typing import List, Optional, Tuple

import aiosqlite

from config import DB_PATH, MAX_QTY
from seed import CATEGORIES, PRODUCTS
from utils import delivery_cost

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    price       INTEGER NOT NULL,
    available   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cart_items (
    user_id    INTEGER NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        INTEGER NOT NULL,
    PRIMARY KEY (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    client_name    TEXT    NOT NULL,
    phone          TEXT    NOT NULL,
    delivery       TEXT    NOT NULL,  -- delivery / pickup
    address        TEXT,
    comment        TEXT    NOT NULL DEFAULT '',
    subtotal       INTEGER NOT NULL,
    delivery_price INTEGER NOT NULL,
    total          INTEGER NOT NULL,
    status         TEXT    NOT NULL DEFAULT 'new',
    created_at     TEXT    NOT NULL
);

-- цена и название копируются в заказ, чтобы изменение каталога не меняло старые заказы
CREATE TABLE IF NOT EXISTS order_items (
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL,
    name       TEXT    NOT NULL,
    price      INTEGER NOT NULL,
    qty        INTEGER NOT NULL
);
"""

CART_QUERY = """
SELECT p.id AS product_id, p.name, p.price, p.available, c.qty
FROM cart_items c JOIN products p ON p.id = c.product_id
WHERE c.user_id = ?
ORDER BY p.category_id, p.id
"""


def _connect():
    return aiosqlite.connect(DB_PATH)


async def init_db() -> None:
    async with _connect() as conn:
        await conn.executescript(SCHEMA)
        cur = await conn.execute("SELECT COUNT(*) FROM products")
        if (await cur.fetchone())[0] == 0:
            cat_ids = []
            for name in CATEGORIES:
                cur = await conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                cat_ids.append(cur.lastrowid)
            await conn.executemany(
                "INSERT INTO products (category_id, name, description, price) VALUES (?, ?, ?, ?)",
                [(cat_ids[c], n, d, p) for c, n, d, p in PRODUCTS],
            )
        await conn.commit()


# ---------- Каталог ----------

async def get_categories() -> List[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM categories ORDER BY id")
        return list(await cur.fetchall())


async def get_category(category_id: int) -> Optional[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        return await cur.fetchone()


async def get_products(category_id: int) -> List[aiosqlite.Row]:
    """Товары категории в наличии."""
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM products WHERE category_id = ? AND available = 1 ORDER BY id",
            (category_id,),
        )
        return list(await cur.fetchall())


async def get_all_products() -> List[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM products ORDER BY category_id, id")
        return list(await cur.fetchall())


async def get_product(product_id: int) -> Optional[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return await cur.fetchone()


async def toggle_product(product_id: int) -> None:
    async with _connect() as conn:
        await conn.execute(
            "UPDATE products SET available = 1 - available WHERE id = ?", (product_id,)
        )
        await conn.commit()


# ---------- Корзина ----------

async def get_cart(user_id: int) -> List[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(CART_QUERY, (user_id,))
        return list(await cur.fetchall())


async def add_to_cart(user_id: int, product_id: int, qty: int) -> None:
    async with _connect() as conn:
        await conn.execute(
            "INSERT INTO cart_items (user_id, product_id, qty) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id, product_id) DO UPDATE SET qty = MIN(qty + excluded.qty, ?)",
            (user_id, product_id, min(qty, MAX_QTY), MAX_QTY),
        )
        await conn.commit()


async def change_cart_qty(user_id: int, product_id: int, delta: int) -> None:
    """Меняет количество; при нуле товар удаляется из корзины."""
    async with _connect() as conn:
        await conn.execute(
            "UPDATE cart_items SET qty = MIN(qty + ?, ?) WHERE user_id = ? AND product_id = ?",
            (delta, MAX_QTY, user_id, product_id),
        )
        await conn.execute("DELETE FROM cart_items WHERE user_id = ? AND qty <= 0", (user_id,))
        await conn.commit()


async def remove_from_cart(user_id: int, product_id: int) -> None:
    async with _connect() as conn:
        await conn.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id)
        )
        await conn.commit()


async def clear_cart(user_id: int) -> None:
    async with _connect() as conn:
        await conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await conn.commit()


# ---------- Заказы ----------

async def create_order(
    user_id: int, client_name: str, phone: str,
    delivery: str, address: Optional[str], comment: str,
) -> Optional[Tuple[int, int]]:
    """Создаёт заказ из товаров корзины в наличии. Возвращает (id, сумма) или None."""
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(CART_QUERY, (user_id,))
        items = [i for i in await cur.fetchall() if i["available"]]
        if not items:
            return None
        subtotal = sum(i["price"] * i["qty"] for i in items)
        delivery_price = delivery_cost(subtotal, delivery)
        total = subtotal + delivery_price
        cur = await conn.execute(
            "INSERT INTO orders (user_id, client_name, phone, delivery, address, comment, "
            "subtotal, delivery_price, total, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, client_name, phone, delivery, address, comment,
             subtotal, delivery_price, total, datetime.now().strftime("%d.%m.%Y %H:%M")),
        )
        order_id = cur.lastrowid
        await conn.executemany(
            "INSERT INTO order_items (order_id, product_id, name, price, qty) VALUES (?, ?, ?, ?, ?)",
            [(order_id, i["product_id"], i["name"], i["price"], i["qty"]) for i in items],
        )
        # товары, которых нет в наличии, остаются в корзине
        await conn.executemany(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
            [(user_id, i["product_id"]) for i in items],
        )
        await conn.commit()
        return order_id, total


async def get_order(order_id: int) -> Optional[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return await cur.fetchone()


async def get_order_items(order_id: int) -> List[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        return list(await cur.fetchall())


async def get_user_orders(user_id: int, limit: int = 5) -> List[aiosqlite.Row]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        )
        return list(await cur.fetchall())


async def get_orders_by_status(statuses: List[str], limit: int = 20) -> List[aiosqlite.Row]:
    marks = ", ".join("?" * len(statuses))
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            f"SELECT * FROM orders WHERE status IN ({marks}) ORDER BY id DESC LIMIT ?",
            (*statuses, limit),
        )
        return list(await cur.fetchall())


async def count_orders(statuses: List[str]) -> int:
    marks = ", ".join("?" * len(statuses))
    async with _connect() as conn:
        cur = await conn.execute(
            f"SELECT COUNT(*) FROM orders WHERE status IN ({marks})", statuses
        )
        return (await cur.fetchone())[0]


async def set_order_status(order_id: int, status: str) -> None:
    async with _connect() as conn:
        await conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await conn.commit()
