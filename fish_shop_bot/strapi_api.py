from io import BytesIO
from urllib.parse import urljoin

import requests


DEFAULT_CART_ITEM_QUANTITY_KG = 1.0
REQUEST_TIMEOUT = 10


def _request(settings: dict, method: str, path: str, **kwargs):
    response = requests.request(
        method,
        f"{settings['api_url']}/{path.lstrip('/')}",
        headers={"Authorization": f"Bearer {settings['token']}"},
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )
    response.raise_for_status()

    return response


def fetch_products(settings: dict) -> list[dict]:
    response = _request(
        settings,
        "GET",
        "products",
        params={"pagination[pageSize]": 100},
    )

    return response.json()["data"]


def fetch_product(settings: dict, product_document_id: str) -> dict:
    response = _request(
        settings,
        "GET",
        f"products/{product_document_id}",
        params={"populate": "image"},
    )

    return response.json()["data"]


def fetch_cart_by_telegram_id(
    settings: dict,
    telegram_id: str,
    *,
    include_items: bool = False,
) -> dict | None:
    params = {
        "filters[telegram_id][$eq]": telegram_id,
        "pagination[pageSize]": 1,
    }
    if include_items:
        params["populate[items][populate][product]"] = "true"

    response = _request(settings, "GET", "carts", params=params)
    carts = response.json()["data"]

    return carts[0] if carts else None


def add_product_to_cart(
    settings: dict,
    telegram_id: str,
    product_document_id: str,
) -> bool:
    cart = fetch_cart_by_telegram_id(settings, telegram_id)
    is_cart_created = cart is None
    if is_cart_created:
        response = _request(
            settings,
            "POST",
            "carts",
            json={"data": {"telegram_id": telegram_id}},
        )
        cart = response.json()["data"]

    _request(
        settings,
        "POST",
        "cart-items",
        json={
            "data": {
                "quantity_kg": DEFAULT_CART_ITEM_QUANTITY_KG,
                "cart": cart["documentId"],
                "product": product_document_id,
            }
        },
    )

    return is_cart_created


def delete_cart_item(settings: dict, cart_item_document_id: str) -> None:
    _request(settings, "DELETE", f"cart-items/{cart_item_document_id}")


def create_customer(settings: dict, telegram_id: str, email: str) -> None:
    _request(
        settings,
        "POST",
        "customers",
        json={"data": {"telegram_id": telegram_id, "email": email}},
    )


def download_product_image(settings: dict, product: dict) -> BytesIO:
    images = product.get("image") or []
    if not images:
        raise RuntimeError(
            f"У товара «{product['title']}» нет картинки"
        )

    image = images[0]
    image_path = image.get("formats", {}).get("small", {}).get("url") or image["url"]
    image_url = urljoin(settings["url"], image_path)
    response = requests.get(image_url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    product_image = BytesIO(response.content)
    product_image.name = image_url.rsplit("/", 1)[-1]

    return product_image
