import logging
import os
from io import BytesIO
from typing import Callable
from urllib.parse import urljoin

import redis
import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from telegram.ext import Filters, MessageHandler, Updater

from fetch_products import (
    DEFAULT_STRAPI_API_URL,
    add_product_to_cart,
    create_customer,
    delete_cart_item,
    fetch_cart_by_telegram_id,
    fetch_product,
    fetch_products,
)


START_STATE = "START"
HANDLE_MENU_STATE = "HANDLE_MENU"
HANDLE_DESCRIPTION_STATE = "HANDLE_DESCRIPTION"
HANDLE_CART_STATE = "HANDLE_CART"
WAITING_EMAIL_STATE = "WAITING_EMAIL"
BACK_TO_PRODUCTS_CALLBACK = "back_to_products"
ADD_TO_CART_CALLBACK_PREFIX = "add_to_cart"
REMOVE_FROM_CART_CALLBACK_PREFIX = "remove_from_cart"
SHOW_CART_CALLBACK = "show_cart"
PAY_CALLBACK = "pay"
USER_STATE_KEY_TEMPLATE = "telegram:{chat_id}:state"

_database = None


def start(update: Update, context: CallbackContext) -> str:
    products_response = fetch_products()
    products = products_response["data"]
    reply_markup = build_products_keyboard(products)
    callback_query = getattr(update, "callback_query", None)
    if callback_query and context:
        chat_id = callback_query.message.chat_id
        context.bot.delete_message(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
        )
        context.bot.send_message(
            chat_id=chat_id,
            text="Привет! Выберите рыбу:",
            reply_markup=reply_markup,
        )
        return HANDLE_MENU_STATE

    update.effective_message.reply_text(
        "Привет! Выберите рыбу:",
        reply_markup=reply_markup,
    )
    return HANDLE_MENU_STATE


def build_products_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for product in products:
        keyboard.append(
            [InlineKeyboardButton(product["title"], callback_data=product["documentId"])]
        )
    keyboard.append(
        [InlineKeyboardButton("Моя корзина", callback_data=SHOW_CART_CALLBACK)]
    )
    return InlineKeyboardMarkup(keyboard)


def handle_menu(update: Update, context: CallbackContext) -> str:
    if not update.callback_query:
        update.effective_message.reply_text("Пожалуйста, выберите товар кнопкой.")
        return HANDLE_MENU_STATE

    product_document_id = get_user_reply(update)
    if product_document_id == BACK_TO_PRODUCTS_CALLBACK:
        return start(update, context)
    if product_document_id == SHOW_CART_CALLBACK:
        send_cart(update)
        return HANDLE_CART_STATE

    product_response = fetch_product(product_document_id)
    product = product_response["data"]
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Добавить в корзину",
                    callback_data=build_add_to_cart_callback(product["documentId"]),
                )
            ],
            [InlineKeyboardButton("Моя корзина", callback_data=SHOW_CART_CALLBACK)],
            [InlineKeyboardButton("Назад", callback_data=BACK_TO_PRODUCTS_CALLBACK)],
        ]
    )
    product_image = download_product_image(product)
    context.bot.delete_message(
        chat_id=update.callback_query.message.chat_id,
        message_id=update.callback_query.message.message_id,
    )
    context.bot.send_photo(
        chat_id=update.callback_query.message.chat_id,
        photo=product_image,
        caption=format_product_details(product),
        reply_markup=reply_markup,
    )
    return HANDLE_DESCRIPTION_STATE


def handle_description(update: Update, context: CallbackContext) -> str:
    if not update.callback_query:
        update.effective_message.reply_text(
            "Пожалуйста, нажмите кнопку «Назад», чтобы вернуться в меню."
        )
        return HANDLE_DESCRIPTION_STATE

    user_reply = get_user_reply(update)
    if user_reply == BACK_TO_PRODUCTS_CALLBACK:
        return start(update, context)

    if user_reply == SHOW_CART_CALLBACK:
        send_cart(update)
        return HANDLE_CART_STATE

    if user_reply and is_add_to_cart_callback(user_reply):
        telegram_id = str(update.callback_query.message.chat_id)
        product_document_id = get_product_document_id_from_cart_callback(user_reply)
        cart, cart_item, is_cart_created = add_product_to_cart(
            telegram_id,
            product_document_id,
        )
        if is_cart_created:
            text = "Корзина создана, товар добавлен."
        else:
            text = "Товар добавлен в корзину."

        update.callback_query.message.reply_text(text)
        logging.info(
            "Позиция корзины %s добавлена в корзину %s для Telegram ID %s",
            cart_item["documentId"],
            cart["documentId"],
            telegram_id,
        )
        return HANDLE_DESCRIPTION_STATE

    update.effective_message.reply_text(
        "Пожалуйста, нажмите кнопку «Назад», чтобы вернуться в меню."
    )
    return HANDLE_DESCRIPTION_STATE


def handle_cart(update: Update, context: CallbackContext) -> str:
    if not update.callback_query:
        update.effective_message.reply_text("Пожалуйста, выберите действие кнопкой.")
        return HANDLE_CART_STATE

    user_reply = get_user_reply(update)
    if user_reply == BACK_TO_PRODUCTS_CALLBACK:
        return start(update, context)

    if user_reply == PAY_CALLBACK:
        update.callback_query.message.reply_text("Напишите вашу почту для связи.")
        return WAITING_EMAIL_STATE

    if user_reply and is_remove_from_cart_callback(user_reply):
        cart_item_document_id = get_cart_item_document_id_from_remove_callback(
            user_reply
        )
        delete_cart_item(cart_item_document_id)
        update.callback_query.message.reply_text("Товар удалён из корзины.")
        send_cart(update)
        return HANDLE_CART_STATE

    update.effective_message.reply_text("Пожалуйста, выберите действие кнопкой.")
    return HANDLE_CART_STATE


def handle_waiting_email(update: Update, context: CallbackContext) -> str:
    if not update.message:
        update.callback_query.message.reply_text("Пожалуйста, отправьте почту текстом.")
        return WAITING_EMAIL_STATE

    email = update.message.text.strip()
    if not is_email(email):
        update.message.reply_text("Похоже, это не почта. Отправьте email ещё раз.")
        return WAITING_EMAIL_STATE

    telegram_id = str(update.message.chat_id)
    customer = create_customer(telegram_id, email)
    logging.info(
        "Клиент %s с почтой %s записан для Telegram ID %s",
        customer["documentId"],
        email,
        telegram_id,
    )
    update.message.reply_text(f"Спасибо! Записал вашу почту: {email}")

    return start(update, context)


def send_cart(update: Update) -> None:
    telegram_id = str(update.callback_query.message.chat_id)
    cart = fetch_cart_by_telegram_id(telegram_id, include_items=True)

    update.callback_query.message.reply_text(
        format_cart(cart),
        reply_markup=build_cart_keyboard(cart),
    )


def build_add_to_cart_callback(product_document_id: str) -> str:
    return f"{ADD_TO_CART_CALLBACK_PREFIX}:{product_document_id}"


def is_add_to_cart_callback(user_reply: str) -> bool:
    return user_reply.startswith(f"{ADD_TO_CART_CALLBACK_PREFIX}:")


def build_remove_from_cart_callback(cart_item_document_id: str) -> str:
    return f"{REMOVE_FROM_CART_CALLBACK_PREFIX}:{cart_item_document_id}"


def is_remove_from_cart_callback(user_reply: str) -> bool:
    return user_reply.startswith(f"{REMOVE_FROM_CART_CALLBACK_PREFIX}:")


def get_product_document_id_from_cart_callback(user_reply: str) -> str:
    return user_reply.removeprefix(f"{ADD_TO_CART_CALLBACK_PREFIX}:")


def get_cart_item_document_id_from_remove_callback(user_reply: str) -> str:
    return user_reply.removeprefix(f"{REMOVE_FROM_CART_CALLBACK_PREFIX}:")


def build_cart_keyboard(cart: dict | None) -> InlineKeyboardMarkup:
    keyboard = []
    if cart and cart.get("items"):
        keyboard.append([InlineKeyboardButton("Оплатить", callback_data=PAY_CALLBACK)])
        for item in cart["items"]:
            product = item["product"]
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"Убрать: {product['title']}",
                        callback_data=build_remove_from_cart_callback(
                            item["documentId"]
                        ),
                    )
                ]
            )
    keyboard.append(
        [InlineKeyboardButton("В меню", callback_data=BACK_TO_PRODUCTS_CALLBACK)]
    )

    return InlineKeyboardMarkup(keyboard)


def is_email(text: str) -> bool:
    _, separator, domain = text.partition("@")
    return bool(separator and "." in domain)


def format_cart(cart: dict | None) -> str:
    if not cart or not cart.get("items"):
        return "Ваша корзина пока пустая."

    total_price = 0
    lines = ["Ваша корзина:"]
    for number, item in enumerate(cart["items"], start=1):
        product = item["product"]
        quantity_kg = item["quantity_kg"]
        product_price = product["price"]
        item_price = product_price * quantity_kg
        total_price += item_price

        lines.extend(
            [
                "",
                f"{number}. {product['title']}",
                (
                    f"{format_quantity_kg(quantity_kg)} × "
                    f"{format_price(product_price)} = {format_price(item_price)}"
                ),
            ]
        )

    lines.extend(["", f"Итого: {format_price(total_price)}"])

    return "\n".join(lines)


def format_quantity_kg(quantity_kg: float) -> str:
    return f"{quantity_kg:g} кг"


def format_price(price: float) -> str:
    return f"{price:g} ₽"


def format_product_details(product: dict) -> str:
    return (
        f"{product['title']}\n\n"
        f"{product['description']}\n\n"
        f"Цена: {product['price']} ₽"
    )


def download_product_image(product: dict) -> BytesIO:
    image_url = get_product_image_url(product)
    response = requests.get(image_url, timeout=10)
    response.raise_for_status()

    image = BytesIO(response.content)
    image.name = image_url.rsplit("/", 1)[-1]
    return image


def get_product_image_url(product: dict) -> str:
    images = product.get("image") or []
    if not images:
        raise RuntimeError(f"У товара «{product['title']}» нет картинки")

    image = images[0]
    image_url = image.get("formats", {}).get("small", {}).get("url") or image["url"]
    strapi_url = os.getenv("STRAPI_URL", DEFAULT_STRAPI_API_URL.removesuffix("/api"))

    return urljoin(strapi_url, image_url)


def handle_users_reply(update: Update, context: CallbackContext) -> None:
    user_reply, chat_id = get_user_reply_and_chat_id(update)
    if user_reply is None or chat_id is None:
        return

    if update.callback_query:
        update.callback_query.answer()

    db = get_database_connection()
    user_state_key = USER_STATE_KEY_TEMPLATE.format(chat_id=chat_id)

    if user_reply == "/start":
        user_state = START_STATE
    else:
        user_state = db.get(user_state_key) or START_STATE

    states_functions: dict[str, Callable[[Update, CallbackContext], str]] = {
        START_STATE: start,
        HANDLE_MENU_STATE: handle_menu,
        HANDLE_DESCRIPTION_STATE: handle_description,
        HANDLE_CART_STATE: handle_cart,
        WAITING_EMAIL_STATE: handle_waiting_email,
    }
    if user_state not in states_functions:
        user_state = START_STATE

    state_handler = states_functions[user_state]
    next_state = state_handler(update, context)
    db.set(user_state_key, next_state)


def get_user_reply(update: Update) -> str | None:
    if update.message:
        return update.message.text
    if update.callback_query:
        return update.callback_query.data
    return None


def get_user_reply_and_chat_id(update: Update) -> tuple[str | None, int | None]:
    if update.message:
        return update.message.text, update.message.chat_id
    if update.callback_query:
        return update.callback_query.data, update.callback_query.message.chat_id
    return None, None


def get_database_connection() -> redis.Redis:
    global _database

    if _database is None:
        database_host = os.getenv("REDIS_HOST", os.getenv("DATABASE_HOST", "localhost"))
        database_port = int(os.getenv("REDIS_PORT", os.getenv("DATABASE_PORT", "6379")))
        database_password = os.getenv("REDIS_PASSWORD") or os.getenv("DATABASE_PASSWORD")
        _database = redis.Redis(
            host=database_host,
            port=database_port,
            password=database_password,
            decode_responses=True,
        )

    return _database


def main() -> None:
    load_dotenv(".env")
    logging.basicConfig(level=logging.INFO)

    token = os.getenv("TG_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("В .env не найден TG_TOKEN")

    get_database_connection().ping()

    updater = Updater(token=token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", handle_users_reply))
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_users_reply))

    updater.start_polling()
    logging.info("Бот рыбного магазина на стейт-машине запущен")
    updater.idle()


if __name__ == "__main__":
    main()
