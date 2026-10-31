import html
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import database as db
import keyboards as kb
from config import ABOUT, FREE_DELIVERY_FROM, SHOP_NAME, STATUSES
from utils import items_text, price, safe_edit

router = Router()


# ---------- Главное меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {html.escape(message.from_user.first_name)}! 👋\n"
        f"Добро пожаловать в <b>{SHOP_NAME}</b>.\n\n"
        "Здесь можно выбрать товары и оформить заказ с доставкой или самовывозом.",
        reply_markup=kb.main_menu(),
    )


@router.message(F.text == kb.BTN_CANCEL)
async def cancel_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Оформление отменено. Товары остались в корзине.", reply_markup=kb.main_menu()
    )


@router.message(F.text == kb.BTN_ABOUT)
async def about(message: Message):
    await message.answer(f"<b>{SHOP_NAME}</b>\n\n{ABOUT}")


@router.message(F.text == kb.BTN_ORDERS)
async def my_orders(message: Message, state: FSMContext):
    await state.clear()
    orders = await db.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer("Вы ещё ничего не заказывали.", reply_markup=kb.main_menu())
        return
    parts = []
    for o in orders:
        items = await db.get_order_items(o["id"])
        parts.append(
            f"<b>Заказ #{o['id']}</b> от {o['created_at']}\n"
            f"{STATUSES[o['status']]}\n{items_text(items)}\n"
            f"Итого: <b>{price(o['total'])}</b>"
        )
    await message.answer("📦 <b>Ваши последние заказы</b>\n\n" + "\n\n".join(parts))


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()


# ---------- Каталог ----------

@router.message(F.text == kb.BTN_CATALOG)
async def catalog(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите категорию:", reply_markup=kb.categories_kb(await db.get_categories()))


@router.callback_query(F.data == "cats")
async def categories(call: CallbackQuery):
    await safe_edit(call, "Выберите категорию:", kb.categories_kb(await db.get_categories()))
    await call.answer()


@router.callback_query(F.data.startswith("cat:"))
async def category(call: CallbackQuery):
    category_id = int(call.data.split(":")[1])
    cat = await db.get_category(category_id)
    products = await db.get_products(category_id)
    if not cat or not products:
        await call.answer("В этой категории пока нет товаров", show_alert=True)
        return
    await safe_edit(call, f"<b>{cat['name']}</b>\n\nВыберите товар:", kb.products_kb(products))
    await call.answer()


@router.callback_query(F.data.startswith("prod:"))
async def product_card(call: CallbackQuery):
    _, pid, qty = call.data.split(":")
    product = await db.get_product(int(pid))
    if not product or not product["available"]:
        await call.answer("Этого товара сейчас нет в наличии", show_alert=True)
        return
    await safe_edit(
        call,
        f"<b>{html.escape(product['name'])}</b>\n\n"
        f"{html.escape(product['description'])}\n\n"
        f"Цена: <b>{price(product['price'])}</b>",
        kb.product_kb(product, int(qty)),
    )
    await call.answer()


@router.callback_query(F.data.startswith("add:"))
async def add_to_cart(call: CallbackQuery):
    _, pid, qty = call.data.split(":")
    product = await db.get_product(int(pid))
    if not product or not product["available"]:
        await call.answer("Этого товара сейчас нет в наличии", show_alert=True)
        return
    await db.add_to_cart(call.from_user.id, product["id"], int(qty))
    await call.answer(f"✅ {product['name']} × {qty} в корзине")


# ---------- Корзина ----------

async def render_cart(user_id: int) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    items = await db.get_cart(user_id)
    if not items:
        return "🛒 Корзина пуста.\n\nЗагляните в каталог!", None
    available = [i for i in items if i["available"]]
    missing = [i for i in items if not i["available"]]
    total = sum(i["price"] * i["qty"] for i in available)
    lines = ["🛒 <b>Корзина</b>\n"]
    if available:
        lines.append(items_text(available))
        lines.append(f"\nСумма: <b>{price(total)}</b>")
        if total < FREE_DELIVERY_FROM:
            lines.append(f"До бесплатной доставки: {price(FREE_DELIVERY_FROM - total)}")
        else:
            lines.append("🎉 Доставка бесплатно!")
    else:
        lines.append("Нет товаров в наличии для заказа.")
    if missing:
        lines.append("\n🚫 Закончились и не войдут в заказ:\n" + "\n".join(
            f"• {html.escape(i['name'])}" for i in missing
        ))
    return "\n".join(lines), kb.cart_kb(items, total)


@router.message(F.text == kb.BTN_CART)
async def cart_message(message: Message, state: FSMContext):
    await state.clear()
    text, markup = await render_cart(message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "cart:show")
async def cart_show(call: CallbackQuery):
    await safe_edit(call, *await render_cart(call.from_user.id))
    await call.answer()


@router.callback_query(F.data.startswith(("cart:inc:", "cart:dec:", "cart:del:")))
async def cart_change(call: CallbackQuery):
    _, action, pid = call.data.split(":")
    if action == "del":
        await db.remove_from_cart(call.from_user.id, int(pid))
    else:
        await db.change_cart_qty(call.from_user.id, int(pid), 1 if action == "inc" else -1)
    await safe_edit(call, *await render_cart(call.from_user.id))
    await call.answer()


@router.callback_query(F.data == "cart:clear")
async def cart_clear(call: CallbackQuery):
    await db.clear_cart(call.from_user.id)
    await safe_edit(call, *await render_cart(call.from_user.id))
    await call.answer("Корзина очищена")
