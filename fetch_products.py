import os
from pprint import pprint

import requests
from dotenv import load_dotenv


DEFAULT_STRAPI_API_URL = "http://localhost:1337/api"


def fetch_products() -> dict:
    load_dotenv()

    strapi_token = os.getenv("STRAPI_TOKEN")
    if not strapi_token:
        raise RuntimeError("STRAPI_TOKEN is missing in .env")

    strapi_api_url = os.getenv("STRAPI_API_URL", DEFAULT_STRAPI_API_URL).rstrip("/")
    response = requests.get(
        f"{strapi_api_url}/products",
        headers={"Authorization": f"Bearer {strapi_token}"},
        params={"pagination[pageSize]": 100},
        timeout=10,
    )
    response.raise_for_status()

    return response.json()


def main() -> None:
    products = fetch_products()
    pprint(products, sort_dicts=False)


if __name__ == "__main__":
    main()
