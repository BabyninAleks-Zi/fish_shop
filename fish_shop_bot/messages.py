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
        item_price = product["price"] * quantity_kg
        total_price += item_price
        lines.extend(
            [
                "",
                f"{number}. {product['title']}",
                (
                    f"{quantity_kg:g} кг × {product['price']:g} ₽ = "
                    f"{item_price:g} ₽"
                ),
            ]
        )

    lines.extend(["", f"Итого: {total_price:g} ₽"])

    return "\n".join(lines)
