import html
from typing import Iterable

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup

from config import DELIVERY_PRICE, FREE_DELIVERY_FROM, STATUSES


def price(value: int) -> str:
    """1200 -> '1 200 ₽'"""
    return f"{value:,}".replace(",", " ") + " ₽"


def delivery_cost(subtotal: int, delivery: str) -> int:
    if delivery != "delivery" or subtotal >= FREE_DELIVERY_FROM:
        return 0
    return DELIVERY_PRICE


def items_text(items: Iterable) -> str:
    return "\n".join(
        f"• {html.escape(i['name'])} × {i['qty']} — {price(i['price'] * i['qty'])}"
        for i in items
    )


def order_text(order, items) -> str:
    lines = [
        f"🧾 <b>Заказ #{order['id']}</b> — {STATUSES[order['status']]}",
        f"🕒 {order['created_at']}",
        "",
        items_text(items),
        "",
        f"Товары: {price(order['subtotal'])}",
    ]
    if order["delivery"] == "delivery":
        lines.append(
            f"Доставка: {price(order['delivery_price']) if order['delivery_price'] else 'бесплатно'}"
        )
    lines += [
        f"<b>Итого: {price(order['total'])}</b>",
        "",
        f"👤 {html.escape(order['client_name'])}, {order['phone']}",
    ]
    if order["delivery"] == "delivery":
        lines.append(f"🚚 Доставка: {html.escape(order['address'])}")
    else:
        lines.append("🏃 Самовывоз")
    if order["comment"]:
        lines.append(f"💬 {html.escape(order['comment'])}")
    return "\n".join(lines)


async def safe_edit(call: CallbackQuery, text: str, markup: InlineKeyboardMarkup = None) -> None:
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
