import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import database as db
import keyboards as kb
from config import ADMIN_ID
from utils import delivery_cost, items_text, order_text, price, safe_edit

router = Router()

PHONE_RE = re.compile(r"^\+?\d{10,15}$")


class Checkout(StatesGroup):
    name = State()
    phone = State()
    delivery = State()
    address = State()
    comment = State()
    confirm = State()


# Шаги: имя → телефон → способ получения → (адрес) → комментарий → подтверждение

@router.callback_query(F.data == "co:start")
async def start_checkout(call: CallbackQuery, state: FSMContext):
    items = [i for i in await db.get_cart(call.from_user.id) if i["available"]]
    if not items:
        await call.answer("В корзине нет товаров в наличии", show_alert=True)
        return
    await state.clear()
    await state.set_state(Checkout.name)
    await call.message.answer("📝 <b>Оформление заказа</b>\n\nКак к вам обращаться?",
                              reply_markup=kb.cancel_kb())
    await call.answer()


@router.message(Checkout.name, F.text)
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Введите имя от 2 до 50 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(Checkout.phone)
    await message.answer(
        "Отправьте номер телефона кнопкой ниже или введите вручную:",
        reply_markup=kb.phone_kb(),
    )


@router.message(Checkout.phone, F.contact | F.text)
async def enter_phone(message: Message, state: FSMContext):
    raw = message.contact.phone_number if message.contact else message.text
    phone = re.sub(r"[\s\-()]", "", raw)
    if not PHONE_RE.match(phone):
        await message.answer("Не похоже на номер телефона. Пример: +79001234567")
        return
    if len(phone) == 11 and phone.startswith("8"):
        phone = "7" + phone[1:]  # 8 900 ... -> +7 900 ...
    if not phone.startswith("+"):
        phone = "+" + phone
    await state.update_data(phone=phone)
    await state.set_state(Checkout.delivery)
    await message.answer("Спасибо!", reply_markup=kb.cancel_kb())
    await message.answer("Как хотите получить заказ?", reply_markup=kb.delivery_kb())


@router.callback_query(Checkout.delivery, F.data == "co:delivery")
async def choose_delivery(call: CallbackQuery, state: FSMContext):
    await state.update_data(delivery="delivery")
    await state.set_state(Checkout.address)
    await safe_edit(call, "Способ получения: 🚚 <b>Доставка</b>")
    await call.message.answer("Введите адрес доставки (улица, дом, квартира):")
    await call.answer()


@router.callback_query(Checkout.delivery, F.data == "co:pickup")
async def choose_pickup(call: CallbackQuery, state: FSMContext):
    await state.update_data(delivery="pickup", address=None)
    await safe_edit(call, "Способ получения: 🏃 <b>Самовывоз</b>")
    await ask_comment(call.message, state)
    await call.answer()


@router.message(Checkout.address, F.text)
async def enter_address(message: Message, state: FSMContext):
    address = message.text.strip()
    if not 5 <= len(address) <= 200:
        await message.answer("Введите адрес от 5 до 200 символов.")
        return
    await state.update_data(address=address)
    await ask_comment(message, state)


async def ask_comment(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.comment)
    await message.answer(
        "Комментарий к заказу? Например, помол кофе или удобное время доставки.",
        reply_markup=kb.skip_kb(),
    )


@router.message(Checkout.comment, F.text)
async def enter_comment(message: Message, state: FSMContext):
    comment = "" if message.text == kb.BTN_SKIP else message.text.strip()[:500]
    await state.update_data(comment=comment)
    await state.set_state(Checkout.confirm)

    data = await state.get_data()
    items = [i for i in await db.get_cart(message.from_user.id) if i["available"]]
    if not items:
        await state.clear()
        await message.answer("Корзина пуста — товары закончились.", reply_markup=kb.main_menu())
        return
    subtotal = sum(i["price"] * i["qty"] for i in items)
    shipping = delivery_cost(subtotal, data["delivery"])
    if data["delivery"] == "delivery":
        receive = f"🚚 Доставка: {html.escape(data['address'])}"
        shipping_line = f"Доставка: {price(shipping) if shipping else 'бесплатно'}\n"
    else:
        receive = "🏃 Самовывоз"
        shipping_line = ""
    text = (
        "Проверьте заказ:\n\n"
        f"{items_text(items)}\n\n"
        f"Товары: {price(subtotal)}\n"
        f"{shipping_line}"
        f"<b>Итого: {price(subtotal + shipping)}</b>\n\n"
        f"👤 {html.escape(data['name'])}, {data['phone']}\n{receive}"
    )
    if comment:
        text += f"\n💬 {html.escape(comment)}"
    await message.answer("Почти готово!", reply_markup=kb.main_menu())
    await message.answer(text, reply_markup=kb.confirm_kb())


@router.callback_query(Checkout.confirm, F.data == "co:confirm")
async def confirm_order(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    result = await db.create_order(
        call.from_user.id, data["name"], data["phone"],
        data["delivery"], data.get("address"), data["comment"],
    )
    await state.clear()
    if result is None:
        await safe_edit(call, "😔 Товары из корзины закончились. Загляните в каталог.")
        await call.answer()
        return

    order_id, total = result
    await safe_edit(
        call,
        f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n"
        f"Сумма: <b>{price(total)}</b>\n"
        "Мы свяжемся с вами для подтверждения. "
        "Статус заказа можно посмотреть в «📦 Мои заказы».",
    )
    await call.answer("Заказ оформлен!")

    if ADMIN_ID:
        order = await db.get_order(order_id)
        try:
            await bot.send_message(
                ADMIN_ID,
                "🔔 <b>Новый заказ!</b>\n\n" + order_text(order, await db.get_order_items(order_id)),
                reply_markup=kb.admin_new_order_kb(order_id),
            )
        except Exception:
            logging.exception("Не удалось уведомить админа о заказе #%s", order_id)


@router.callback_query(F.data == "co:cancel")
async def cancel_checkout(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(call, "Оформление отменено. Товары остались в корзине.")
    await call.answer()


@router.callback_query(F.data.startswith("co:"))
async def stale_button(call: CallbackQuery):
    await call.answer("Эта кнопка устарела. Откройте корзину заново.", show_alert=True)
