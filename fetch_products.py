import os
from pprint import pprint

import requests
from dotenv import load_dotenv


DEFAULT_STRAPI_API_URL = "http://localhost:1337/api"
DEFAULT_CART_ITEM_QUANTITY_KG = 1.0


def get_strapi_api_settings() -> tuple[str, dict[str, str]]:
    load_dotenv(".env")

    strapi_token = os.getenv("STRAPI_TOKEN")
    if not strapi_token:
        raise RuntimeError("В .env не найден STRAPI_TOKEN")

    strapi_api_url = os.getenv("STRAPI_API_URL", DEFAULT_STRAPI_API_URL).rstrip("/")
    headers = {"Authorization": f"Bearer {strapi_token}"}

    return strapi_api_url, headers


def fetch_products() -> dict:
    strapi_api_url, headers = get_strapi_api_settings()
    response = requests.get(
        f"{strapi_api_url}/products",
        headers=headers,
        params={"pagination[pageSize]": 100},
        timeout=10,
    )
    response.raise_for_status()

    return response.json()


def fetch_product(product_document_id: str) -> dict:
    strapi_api_url, headers = get_strapi_api_settings()
    response = requests.get(
        f"{strapi_api_url}/products/{product_document_id}",
        headers=headers,
        params={"populate": "image"},
        timeout=10,
    )
    response.raise_for_status()

    return response.json()


def fetch_cart_by_telegram_id(
    telegram_id: str,
    *,
    include_items: bool = False,
) -> dict | None:
    strapi_api_url, headers = get_strapi_api_settings()
    params = {
        "filters[telegram_id][$eq]": telegram_id,
        "pagination[pageSize]": 1,
    }
    if include_items:
        params["populate[items][populate][product]"] = "true"

    response = requests.get(
        f"{strapi_api_url}/carts",
        headers=headers,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    carts = response.json()["data"]
    return carts[0] if carts else None


def create_cart(telegram_id: str) -> dict:
    strapi_api_url, headers = get_strapi_api_settings()
    response = requests.post(
        f"{strapi_api_url}/carts",
        headers=headers,
        json={"data": {"telegram_id": telegram_id}},
        timeout=10,
    )
    response.raise_for_status()

    return response.json()["data"]


def get_or_create_cart(telegram_id: str) -> tuple[dict, bool]:
    cart = fetch_cart_by_telegram_id(telegram_id)
    if cart:
        return cart, False

    return create_cart(telegram_id), True


def create_cart_item(
    cart_document_id: str,
    product_document_id: str,
    quantity_kg: float = DEFAULT_CART_ITEM_QUANTITY_KG,
) -> dict:
    strapi_api_url, headers = get_strapi_api_settings()
    response = requests.post(
        f"{strapi_api_url}/cart-items",
        headers=headers,
        json={
            "data": {
                "quantity_kg": quantity_kg,
                "cart": cart_document_id,
                "product": product_document_id,
            }
        },
        timeout=10,
    )
    response.raise_for_status()

    return response.json()["data"]


def add_product_to_cart(
    telegram_id: str,
    product_document_id: str,
) -> tuple[dict, dict, bool]:
    cart, is_cart_created = get_or_create_cart(telegram_id)
    cart_item = create_cart_item(cart["documentId"], product_document_id)

    return cart, cart_item, is_cart_created


def delete_cart_item(cart_item_document_id: str) -> dict:
    strapi_api_url, headers = get_strapi_api_settings()
    response = requests.delete(
        f"{strapi_api_url}/cart-items/{cart_item_document_id}",
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()

    return {"documentId": cart_item_document_id}


def create_customer(telegram_id: str, email: str) -> dict:
    strapi_api_url, headers = get_strapi_api_settings()
    response = requests.post(
        f"{strapi_api_url}/customers",
        headers=headers,
        json={"data": {"telegram_id": telegram_id, "email": email}},
        timeout=10,
    )
    response.raise_for_status()

    return response.json()["data"]


def fetch_customer_by_email(email: str) -> dict | None:
    strapi_api_url, headers = get_strapi_api_settings()
    response = requests.get(
        f"{strapi_api_url}/customers",
        headers=headers,
        params={
            "filters[email][$eq]": email,
            "pagination[pageSize]": 1,
        },
        timeout=10,
    )
    response.raise_for_status()

    customers = response.json()["data"]
    return customers[0] if customers else None


def main() -> None:
    products = fetch_products()
    pprint(products, sort_dicts=False)


if __name__ == "__main__":
    main()
