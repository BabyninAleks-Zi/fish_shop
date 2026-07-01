from io import BytesIO
from urllib.parse import urljoin

import requests

from utils.config import get_strapi_api_url, get_strapi_token, get_strapi_url


DEFAULT_CART_ITEM_QUANTITY_KG = 1.0
REQUEST_TIMEOUT = 10


def _request(method: str, path: str, **kwargs):
    strapi_api_url = get_strapi_api_url()
    strapi_token = get_strapi_token()
    response = requests.request(
        method,
        f"{strapi_api_url}/{path.lstrip('/')}",
        headers={"Authorization": f"Bearer {strapi_token}"},
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )
    response.raise_for_status()

    return response


def fetch_products() -> list[dict]:
    response = _request(
        "GET",
        "products",
        params={"pagination[pageSize]": 100},
    )

    return response.json()["data"]


def fetch_product(product_document_id: str) -> dict:
    response = _request(
        "GET",
        f"products/{product_document_id}",
        params={"populate": "image"},
    )

    return response.json()["data"]


def fetch_cart_by_telegram_id(
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

    response = _request("GET", "carts", params=params)
    carts = response.json()["data"]

    return carts[0] if carts else None


def _create_cart(telegram_id: str) -> dict:
    response = _request(
        "POST",
        "carts",
        json={"data": {"telegram_id": telegram_id}},
    )

    return response.json()["data"]


def _get_or_create_cart(telegram_id: str) -> tuple[dict, bool]:
    cart = fetch_cart_by_telegram_id(telegram_id)
    if cart:
        return cart, False

    return _create_cart(telegram_id), True


def _create_cart_item(
    cart_document_id: str,
    product_document_id: str,
    quantity_kg: float = DEFAULT_CART_ITEM_QUANTITY_KG,
) -> dict:
    response = _request(
        "POST",
        "cart-items",
        json={
            "data": {
                "quantity_kg": quantity_kg,
                "cart": cart_document_id,
                "product": product_document_id,
            }
        },
    )

    return response.json()["data"]


def add_product_to_cart(
    telegram_id: str,
    product_document_id: str,
) -> tuple[dict, dict, bool]:
    cart, is_cart_created = _get_or_create_cart(telegram_id)
    cart_item = _create_cart_item(cart["documentId"], product_document_id)

    return cart, cart_item, is_cart_created


def delete_cart_item(cart_item_document_id: str) -> dict:
    _request("DELETE", f"cart-items/{cart_item_document_id}")

    return {"documentId": cart_item_document_id}


def create_customer(telegram_id: str, email: str) -> dict:
    response = _request(
        "POST",
        "customers",
        json={"data": {"telegram_id": telegram_id, "email": email}},
    )

    return response.json()["data"]


def download_product_image(product: dict) -> BytesIO:
    image_url = _get_product_image_url(product)
    response = requests.get(image_url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    image = BytesIO(response.content)
    image.name = image_url.rsplit("/", 1)[-1]

    return image


def _get_product_image_url(product: dict) -> str:
    images = product.get("image") or []
    if not images:
        raise RuntimeError(f"У товара «{product['title']}» нет картинки")

    image = images[0]
    image_url = image.get("formats", {}).get("small", {}).get("url") or image["url"]

    return urljoin(get_strapi_url(), image_url)
