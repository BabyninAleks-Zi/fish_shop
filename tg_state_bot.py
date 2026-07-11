import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from telegram.ext import ConversationHandler, Filters, MessageHandler, Updater

from fish_shop_bot.keyboards import (
    ADD_TO_CART_CALLBACK_PREFIX,
    BACK_TO_PRODUCTS_CALLBACK,
    PAY_CALLBACK,
    REMOVE_FROM_CART_CALLBACK_PREFIX,
    SHOW_CART_CALLBACK,
    build_cart_keyboard,
    build_product_keyboard,
    build_products_keyboard,
)
from fish_shop_bot.messages import format_cart, format_product_details
from fish_shop_bot.strapi_api import (
    add_product_to_cart,
    create_customer,
    delete_cart_item,
    download_product_image,
    fetch_cart_by_telegram_id,
    fetch_product,
    fetch_products,
)


MENU, PRODUCT, CART, EMAIL = range(4)


def show_menu(update: Update, context: CallbackContext) -> int:
    reply_markup = build_products_keyboard(fetch_products(context.bot_data["strapi"]))
    query = update.callback_query

    if query:
        context.bot.delete_message(
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
        )
        context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Привет! Выберите рыбу:",
            reply_markup=reply_markup,
        )
    else:
        update.message.reply_text(
            "Привет! Выберите рыбу:",
            reply_markup=reply_markup,
        )

    return MENU


def handle_menu(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == SHOW_CART_CALLBACK:
        show_cart(query, context)
        return CART

    product = fetch_product(context.bot_data["strapi"], query.data)
    product_image = download_product_image(context.bot_data["strapi"], product)
    context.bot.delete_message(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
    )
    context.bot.send_photo(
        chat_id=query.message.chat_id,
        photo=product_image,
        caption=format_product_details(product),
        reply_markup=build_product_keyboard(product),
    )

    return PRODUCT


def handle_product(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == BACK_TO_PRODUCTS_CALLBACK:
        return show_menu(update, context)

    if query.data == SHOW_CART_CALLBACK:
        show_cart(query, context)
        return CART

    if query.data.startswith(ADD_TO_CART_CALLBACK_PREFIX):
        telegram_id = str(query.message.chat_id)
        product_document_id = query.data.removeprefix(ADD_TO_CART_CALLBACK_PREFIX)
        is_cart_created = add_product_to_cart(
            context.bot_data["strapi"],
            telegram_id,
            product_document_id,
        )
        if is_cart_created:
            text = "Корзина создана, товар добавлен."
        else:
            text = "Товар добавлен в корзину."

        query.message.reply_text(text)
        logging.info(
            "Товар добавлен в корзину пользователя %s",
            telegram_id,
        )

    return PRODUCT


def handle_cart(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == BACK_TO_PRODUCTS_CALLBACK:
        return show_menu(update, context)

    if query.data == PAY_CALLBACK:
        query.message.reply_text(
            "Напишите вашу почту для связи."
        )
        return EMAIL

    if query.data.startswith(REMOVE_FROM_CART_CALLBACK_PREFIX):
        cart_item_document_id = query.data.removeprefix(
            REMOVE_FROM_CART_CALLBACK_PREFIX
        )
        delete_cart_item(context.bot_data["strapi"], cart_item_document_id)
        query.message.reply_text("Товар удалён из корзины.")
        show_cart(query, context)

    return CART


def handle_email(update: Update, context: CallbackContext) -> int:
    email = update.message.text.strip()
    _, separator, domain = email.partition("@")
    if not separator or "." not in domain:
        update.message.reply_text(
            "Похоже, это не почта. "
            "Отправьте email ещё раз."
        )
        return EMAIL

    telegram_id = str(update.message.chat_id)
    create_customer(context.bot_data["strapi"], telegram_id, email)
    logging.info(
        "Почта клиента записана для Telegram ID %s",
        telegram_id,
    )
    update.message.reply_text(
        f"Спасибо! Записал вашу почту: {email}"
    )

    return show_menu(update, context)


def show_cart(query, context: CallbackContext) -> None:
    telegram_id = str(query.message.chat_id)
    cart = fetch_cart_by_telegram_id(
        context.bot_data["strapi"],
        telegram_id,
        include_items=True,
    )
    query.message.reply_text(
        format_cart(cart),
        reply_markup=build_cart_keyboard(cart),
    )


def main() -> None:
    load_dotenv()
    required_variables = (
        "TG_TOKEN",
        "STRAPI_TOKEN",
        "STRAPI_API_URL",
        "STRAPI_URL",
    )
    missing_variables = [
        variable for variable in required_variables if not os.getenv(variable)
    ]
    if missing_variables:
        raise RuntimeError(
            "В .env не заполнены переменные: "
            f"{', '.join(missing_variables)}"
        )

    logging.basicConfig(level=logging.INFO)
    updater = Updater(token=os.environ["TG_TOKEN"])
    dispatcher = updater.dispatcher
    dispatcher.bot_data["strapi"] = {
        "api_url": os.environ["STRAPI_API_URL"].rstrip("/"),
        "url": os.environ["STRAPI_URL"].rstrip("/"),
        "token": os.environ["STRAPI_TOKEN"],
    }
    dispatcher.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("start", show_menu)],
            states={
                MENU: [CallbackQueryHandler(handle_menu)],
                PRODUCT: [CallbackQueryHandler(handle_product)],
                CART: [CallbackQueryHandler(handle_cart)],
                EMAIL: [MessageHandler(Filters.text & ~Filters.command, handle_email)],
            },
            fallbacks=[CommandHandler("start", show_menu)],
        )
    )

    updater.start_polling()
    logging.info("Бот рыбного магазина запущен")
    updater.idle()


if __name__ == "__main__":
    main()
