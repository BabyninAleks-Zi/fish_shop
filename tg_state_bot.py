import logging

from telegram import Update
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler
from telegram.ext import Filters, MessageHandler, Updater

from utils.config import get_telegram_token
from utils.storage import get_database_connection
from utils.strapi_api import (
    add_product_to_cart,
    create_customer,
    delete_cart_item,
    download_product_image,
    fetch_cart_by_telegram_id,
    fetch_product,
    fetch_products,
)
from utils.telegram_ui import (
    BACK_TO_PRODUCTS_CALLBACK,
    PAY_CALLBACK,
    SHOW_CART_CALLBACK,
    build_cart_keyboard,
    build_product_keyboard,
    build_products_keyboard,
    format_cart,
    format_product_details,
    get_cart_item_document_id_from_remove_callback,
    get_product_document_id_from_cart_callback,
    is_add_to_cart_callback,
    is_email,
    is_remove_from_cart_callback,
)


START_STATE = "START"
HANDLE_MENU_STATE = "HANDLE_MENU"
HANDLE_DESCRIPTION_STATE = "HANDLE_DESCRIPTION"
HANDLE_CART_STATE = "HANDLE_CART"
WAITING_EMAIL_STATE = "WAITING_EMAIL"
USER_STATE_KEY_TEMPLATE = "telegram:{chat_id}:state"


def start(update: Update, context: CallbackContext) -> str:
    reply_markup = build_products_keyboard(fetch_products())
    callback_query = getattr(update, "callback_query", None)
    if callback_query:
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


def handle_menu(update: Update, context: CallbackContext) -> str:
    if not update.callback_query:
        update.effective_message.reply_text("Пожалуйста, выберите товар кнопкой.")
        return HANDLE_MENU_STATE

    user_reply = get_user_reply(update)
    if user_reply == BACK_TO_PRODUCTS_CALLBACK:
        return start(update, context)

    if user_reply == SHOW_CART_CALLBACK:
        send_cart(update)
        return HANDLE_CART_STATE

    product = fetch_product(user_reply)
    product_image = download_product_image(product)
    context.bot.delete_message(
        chat_id=update.callback_query.message.chat_id,
        message_id=update.callback_query.message.message_id,
    )
    context.bot.send_photo(
        chat_id=update.callback_query.message.chat_id,
        photo=product_image,
        caption=format_product_details(product),
        reply_markup=build_product_keyboard(product),
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

    states_functions = {
        START_STATE: start,
        HANDLE_MENU_STATE: handle_menu,
        HANDLE_DESCRIPTION_STATE: handle_description,
        HANDLE_CART_STATE: handle_cart,
        WAITING_EMAIL_STATE: handle_waiting_email,
    }
    state_handler = states_functions.get(user_state, start)
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


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    get_database_connection().ping()

    updater = Updater(token=get_telegram_token())
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", handle_users_reply))
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(
        MessageHandler(Filters.text & ~Filters.command, handle_users_reply)
    )

    updater.start_polling()
    logging.info("Бот рыбного магазина на стейт-машине запущен")
    updater.idle()


if __name__ == "__main__":
    main()
