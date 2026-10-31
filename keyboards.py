from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import DELIVERY_PRICE, FREE_DELIVERY_FROM, MAX_QTY, STATUSES
from utils import price

BTN_CATALOG = "🛍 Каталог"
BTN_CART = "🛒 Корзина"
BTN_ORDERS = "📦 Мои заказы"
BTN_ABOUT = "ℹ️ О магазине"
BTN_CANCEL = "❌ Отмена"
BTN_SKIP = "➡️ Пропустить"


def _short(name: str, limit: int = 22) -> str:
    return name if len(name) <= limit else name[: limit - 1] + "…"


# ---------- Reply-клавиатуры ----------

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_CART)],
            [KeyboardButton(text=BTN_ORDERS), KeyboardButton(text=BTN_ABOUT)],
        ],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_SKIP), KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


# ---------- Inline: каталог и корзина ----------

def categories_kb(categories) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in categories:
        b.button(text=c["name"], callback_data=f"cat:{c['id']}")
    b.button(text="🛒 Корзина", callback_data="cart:show")
    b.adjust(1)
    return b.as_markup()


def products_kb(products) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=f"{p['name']} — {price(p['price'])}", callback_data=f"prod:{p['id']}:1")
    b.button(text="⬅️ Категории", callback_data="cats")
    b.button(text="🛒 Корзина", callback_data="cart:show")
    b.adjust(*([1] * len(products)), 2)
    return b.as_markup()


def product_kb(product, qty: int) -> InlineKeyboardMarkup:
    pid = product["id"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➖", callback_data=f"prod:{pid}:{max(qty - 1, 1)}"),
            InlineKeyboardButton(text=f"{qty} шт.", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"prod:{pid}:{min(qty + 1, MAX_QTY)}"),
        ],
        [InlineKeyboardButton(
            text=f"🛒 В корзину · {price(product['price'] * qty)}",
            callback_data=f"add:{pid}:{qty}",
        )],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat:{product['category_id']}"),
            InlineKeyboardButton(text="🛒 Корзина", callback_data="cart:show"),
        ],
    ])


def cart_kb(items, total: int) -> InlineKeyboardMarkup:
    rows = []
    for i in items:
        pid = i["product_id"]
        if i["available"]:
            rows.append([
                InlineKeyboardButton(text="➖", callback_data=f"cart:dec:{pid}"),
                InlineKeyboardButton(text=f"{_short(i['name'], 16)} × {i['qty']}", callback_data="noop"),
                InlineKeyboardButton(text="➕", callback_data=f"cart:inc:{pid}"),
                InlineKeyboardButton(text="🗑", callback_data=f"cart:del:{pid}"),
            ])
        else:
            rows.append([
                InlineKeyboardButton(text=f"🚫 {_short(i['name'])}", callback_data="noop"),
                InlineKeyboardButton(text="🗑", callback_data=f"cart:del:{pid}"),
            ])
    if total:
        rows.append([InlineKeyboardButton(
            text=f"✅ Оформить заказ · {price(total)}", callback_data="co:start"
        )])
    rows.append([
        InlineKeyboardButton(text="🧹 Очистить", callback_data="cart:clear"),
        InlineKeyboardButton(text="🛍 Каталог", callback_data="cats"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- Inline: оформление ----------

def delivery_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=f"🚚 Доставка ({price(DELIVERY_PRICE)}, от {price(FREE_DELIVERY_FROM)} — бесплатно)",
        callback_data="co:delivery",
    )
    b.button(text="🏃 Самовывоз", callback_data="co:pickup")
    b.adjust(1)
    return b.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить заказ", callback_data="co:confirm")
    b.button(text="✖️ Отменить", callback_data="co:cancel")
    b.adjust(1)
    return b.as_markup()


# ---------- Inline: админка ----------

def admin_menu(new_count: int, active_count: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"🆕 Новые ({new_count})", callback_data="adm:list:new")
    b.button(text=f"🔄 В работе ({active_count})", callback_data="adm:list:active")
    b.button(text="📁 Завершённые", callback_data="adm:list:closed")
    b.button(text="📋 Наличие товаров", callback_data="adm:products")
    b.adjust(2, 1, 1)
    return b.as_markup()


def admin_orders_kb(orders) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in orders:
        b.button(
            text=f"#{o['id']} · {price(o['total'])} · {_short(o['client_name'], 14)}",
            callback_data=f"adm:order:{o['id']}",
        )
    b.button(text="⬅️ Меню", callback_data="adm:menu")
    b.adjust(1)
    return b.as_markup()


def admin_order_kb(order) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for status, label in STATUSES.items():
        if status not in ("new", order["status"]):
            b.button(text=label, callback_data=f"adm:st:{order['id']}:{status}")
    b.button(text="⬅️ Меню", callback_data="adm:menu")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def admin_new_order_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Открыть заказ", callback_data=f"adm:order:{order_id}")
    return b.as_markup()


def admin_products_kb(products) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        icon = "✅" if p["available"] else "🚫"
        b.button(text=f"{icon} {p['name']}", callback_data=f"adm:toggle:{p['id']}")
    b.button(text="⬅️ Меню", callback_data="adm:menu")
    b.adjust(1)
    return b.as_markup()
