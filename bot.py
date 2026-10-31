import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

import database as db
from config import ADMIN_ID, BOT_TOKEN
from handlers import admin, checkout, shop


async def main() -> None:
    if not BOT_TOKEN:
        sys.exit("Не задан BOT_TOKEN. Скопируйте .env.example в .env и впишите токен.")
    if not ADMIN_ID:
        logging.warning("ADMIN_ID не задан — уведомления о заказах и /admin работать не будут")

    await db.init_db()

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    # shop идёт раньше checkout, чтобы кнопки меню работали посреди оформления
    dp.include_routers(admin.router, shop.router, checkout.router)

    await bot.set_my_commands([BotCommand(command="start", description="Главное меню")])

    try:
        logging.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main())
