from telegram import InlineKeyboardButton, InlineKeyboardMarkup


BACK_TO_PRODUCTS_CALLBACK = "back_to_products"
ADD_TO_CART_CALLBACK_PREFIX = "add_to_cart:"
REMOVE_FROM_CART_CALLBACK_PREFIX = "remove_from_cart:"
SHOW_CART_CALLBACK = "show_cart"
PAY_CALLBACK = "pay"


def build_products_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(product["title"], callback_data=product["documentId"])]
        for product in products
    ]
    cart_button = InlineKeyboardButton(
        "Моя корзина",
        callback_data=SHOW_CART_CALLBACK,
    )
    keyboard.append([cart_button])

    return InlineKeyboardMarkup(keyboard)


def build_product_keyboard(product: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Добавить в корзину",
                    callback_data=(
                        f"{ADD_TO_CART_CALLBACK_PREFIX}{product['documentId']}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    "Моя корзина",
                    callback_data=SHOW_CART_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    "Назад",
                    callback_data=BACK_TO_PRODUCTS_CALLBACK,
                )
            ],
        ]
    )


def build_cart_keyboard(cart: dict | None) -> InlineKeyboardMarkup:
    keyboard = []
    if cart and cart.get("items"):
        pay_button = InlineKeyboardButton(
            "Оплатить",
            callback_data=PAY_CALLBACK,
        )
        keyboard.append([pay_button])
        for item in cart["items"]:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"Убрать: {item['product']['title']}",
                        callback_data=(
                            f"{REMOVE_FROM_CART_CALLBACK_PREFIX}{item['documentId']}"
                        ),
                    )
                ]
            )
    keyboard.append(
        [InlineKeyboardButton("В меню", callback_data=BACK_TO_PRODUCTS_CALLBACK)]
    )

    return InlineKeyboardMarkup(keyboard)
