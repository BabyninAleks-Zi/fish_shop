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

from fetch_products import DEFAULT_STRAPI_API_URL, fetch_product, fetch_products


START_STATE = "START"
HANDLE_MENU_STATE = "HANDLE_MENU"
HANDLE_DESCRIPTION_STATE = "HANDLE_DESCRIPTION"
BACK_TO_PRODUCTS_CALLBACK = "back_to_products"
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
    return InlineKeyboardMarkup(keyboard)


def handle_menu(update: Update, context: CallbackContext) -> str:
    if not update.callback_query:
        update.effective_message.reply_text("Пожалуйста, выберите товар кнопкой.")
        return HANDLE_MENU_STATE

    product_document_id = get_user_reply(update)
    if product_document_id == BACK_TO_PRODUCTS_CALLBACK:
        return start(update, context)

    product_response = fetch_product(product_document_id)
    product = product_response["data"]
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Назад", callback_data=BACK_TO_PRODUCTS_CALLBACK)]]
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

    update.effective_message.reply_text(
        "Пожалуйста, нажмите кнопку «Назад», чтобы вернуться в меню."
    )
    return HANDLE_DESCRIPTION_STATE


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
