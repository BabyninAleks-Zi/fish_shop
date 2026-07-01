import os

from dotenv import load_dotenv


DEFAULT_STRAPI_API_URL = "http://localhost:1337/api"

_is_environment_loaded = False


def load_environment(env_file: str = ".env") -> None:
    global _is_environment_loaded

    if not _is_environment_loaded:
        load_dotenv(env_file)
        _is_environment_loaded = True


def get_telegram_token() -> str:
    load_environment()

    token = os.getenv("TG_TOKEN") or os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("В .env не найден TG_TOKEN")

    return token


def get_redis_settings() -> dict:
    load_environment()

    return {
        "host": os.getenv("REDIS_HOST", os.getenv("DATABASE_HOST", "localhost")),
        "port": int(os.getenv("REDIS_PORT", os.getenv("DATABASE_PORT", "6379"))),
        "password": os.getenv("REDIS_PASSWORD") or os.getenv("DATABASE_PASSWORD"),
    }


def get_strapi_api_url() -> str:
    load_environment()

    return os.getenv("STRAPI_API_URL", DEFAULT_STRAPI_API_URL).rstrip("/")


def get_strapi_url() -> str:
    load_environment()

    strapi_api_url = get_strapi_api_url()
    return os.getenv("STRAPI_URL", strapi_api_url.removesuffix("/api")).rstrip("/")


def get_strapi_token() -> str:
    load_environment()

    token = os.getenv("STRAPI_TOKEN")
    if not token:
        raise RuntimeError("В .env не найден STRAPI_TOKEN")

    return token
