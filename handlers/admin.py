import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import ADMIN_ID, STATUSES
from utils import order_text, safe_edit

router = Router()
# все хендлеры этого роутера доступны только админу
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)

ORDER_GROUPS = {
    "new": (["new"], "🆕 Новые заказы"),
    "active": (["accepted", "assembling", "shipping"], "🔄 Заказы в работе"),
    "closed": (["done", "cancelled"], "📁 Завершённые заказы"),
}

# что написать клиенту при смене статуса
CLIENT_MESSAGES = {
    "accepted": "✅ Ваш заказ #{id} принят и скоро будет собран.",
    "assembling": "📦 Ваш заказ #{id} собирается.",
    "shipping": "🚚 Ваш заказ #{id} передан в доставку.",
    "done": "🎉 Заказ #{id} выполнен. Спасибо за покупку!",
    "cancelled": "❌ К сожалению, заказ #{id} отменён. Если есть вопросы — свяжитесь с нами.",
}


async def menu_markup():
    new = await db.count_orders(ORDER_GROUPS["new"][0])
    active = await db.count_orders(ORDER_GROUPS["active"][0])
    return kb.admin_menu(new, active)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("🛠 <b>Панель администратора</b>", reply_markup=await menu_markup())


@router.callback_query(F.data == "adm:menu")
async def adm_menu(call: CallbackQuery):
    await safe_edit(call, "🛠 <b>Панель администратора</b>", await menu_markup())
    await call.answer()


@router.callback_query(F.data.startswith("adm:list:"))
async def adm_list(call: CallbackQuery):
    statuses, title = ORDER_GROUPS[call.data.split(":")[2]]
    orders = await db.get_orders_by_status(statuses)
    text = f"<b>{title}</b>\n\n" + ("Выберите заказ:" if orders else "Пока пусто.")
    await safe_edit(call, text, kb.admin_orders_kb(orders))
    await call.answer()


async def show_order(call: CallbackQuery, order_id: int) -> None:
    order = await db.get_order(order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    items = await db.get_order_items(order_id)
    await safe_edit(
        call,
        order_text(order, items) + "\n\n<i>Изменить статус:</i>",
        kb.admin_order_kb(order),
    )


@router.callback_query(F.data.startswith("adm:order:"))
async def adm_order(call: CallbackQuery):
    await show_order(call, int(call.data.split(":")[2]))
    await call.answer()


@router.callback_query(F.data.startswith("adm:st:"))
async def adm_status(call: CallbackQuery, bot: Bot):
    _, _, order_id, status = call.data.split(":")
    order = await db.get_order(int(order_id))
    if not order or status not in STATUSES:
        await call.answer("Заказ не найден", show_alert=True)
        return
    await db.set_order_status(order["id"], status)
    await call.answer(f"Статус: {STATUSES[status]}")
    try:
        await bot.send_message(order["user_id"], CLIENT_MESSAGES[status].format(id=order["id"]))
    except Exception:
        logging.exception("Не удалось уведомить клиента о заказе #%s", order["id"])
    await show_order(call, order["id"])


async def show_products(call: CallbackQuery) -> None:
    await safe_edit(
        call,
        "📋 <b>Наличие товаров</b>\n\nНажмите на товар, чтобы скрыть его из каталога или вернуть.",
        kb.admin_products_kb(await db.get_all_products()),
    )


@router.callback_query(F.data == "adm:products")
async def adm_products(call: CallbackQuery):
    await show_products(call)
    await call.answer()


@router.callback_query(F.data.startswith("adm:toggle:"))
async def adm_toggle(call: CallbackQuery):
    product_id = int(call.data.split(":")[2])
    await db.toggle_product(product_id)
    product = await db.get_product(product_id)
    await call.answer(("✅ В наличии: " if product["available"] else "🚫 Скрыт: ") + product["name"])
    await show_products(call)
