import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "shop.db")

# Данные магазина — меняются под конкретного заказчика
SHOP_NAME = "Кофейная лавка «Зерно»"
ABOUT = (
    "Свежеобжаренный кофе, чай и всё для заваривания.\n\n"
    "📍 Самовывоз: ул. Ленина, 25 (ежедневно 9:00–21:00)\n"
    "🚚 Доставка по городу в день заказа\n"
    "📞 +7 (900) 765-43-21"
)

DELIVERY_PRICE = 300        # стоимость доставки, ₽
FREE_DELIVERY_FROM = 3000   # бесплатная доставка от этой суммы, ₽
MAX_QTY = 20                # максимум одного товара в заказе

# Статусы заказа в порядке выполнения
STATUSES = {
    "new": "🆕 Новый",
    "accepted": "✅ Принят",
    "assembling": "📦 Собирается",
    "shipping": "🚚 Передан в доставку",
    "done": "🎉 Выполнен",
    "cancelled": "❌ Отменён",
}
