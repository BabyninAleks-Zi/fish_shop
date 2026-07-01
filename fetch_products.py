import os
from pprint import pprint

import requests
from dotenv import load_dotenv


DEFAULT_STRAPI_API_URL = "http://localhost:1337/api"


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


def main() -> None:
    products = fetch_products()
    pprint(products, sort_dicts=False)


if __name__ == "__main__":
    main()
