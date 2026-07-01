from telegram import InlineKeyboardButton, InlineKeyboardMarkup


BACK_TO_PRODUCTS_CALLBACK = "back_to_products"
ADD_TO_CART_CALLBACK_PREFIX = "add_to_cart"
REMOVE_FROM_CART_CALLBACK_PREFIX = "remove_from_cart"
SHOW_CART_CALLBACK = "show_cart"
PAY_CALLBACK = "pay"


def build_products_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(product["title"], callback_data=product["documentId"])]
        for product in products
    ]
    keyboard.append(
        [InlineKeyboardButton("Моя корзина", callback_data=SHOW_CART_CALLBACK)]
    )

    return InlineKeyboardMarkup(keyboard)


def build_product_keyboard(product: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
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


def build_add_to_cart_callback(product_document_id: str) -> str:
    return f"{ADD_TO_CART_CALLBACK_PREFIX}:{product_document_id}"


def is_add_to_cart_callback(user_reply: str) -> bool:
    return user_reply.startswith(f"{ADD_TO_CART_CALLBACK_PREFIX}:")


def get_product_document_id_from_cart_callback(user_reply: str) -> str:
    return user_reply.removeprefix(f"{ADD_TO_CART_CALLBACK_PREFIX}:")


def build_remove_from_cart_callback(cart_item_document_id: str) -> str:
    return f"{REMOVE_FROM_CART_CALLBACK_PREFIX}:{cart_item_document_id}"


def is_remove_from_cart_callback(user_reply: str) -> bool:
    return user_reply.startswith(f"{REMOVE_FROM_CART_CALLBACK_PREFIX}:")


def get_cart_item_document_id_from_remove_callback(user_reply: str) -> str:
    return user_reply.removeprefix(f"{REMOVE_FROM_CART_CALLBACK_PREFIX}:")


def format_product_details(product: dict) -> str:
    return (
        f"{product['title']}\n\n"
        f"{product['description']}\n\n"
        f"Цена: {product['price']} ₽"
    )


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


def is_email(text: str) -> bool:
    _, separator, domain = text.partition("@")

    return bool(separator and "." in domain)
