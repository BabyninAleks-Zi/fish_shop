import redis

from utils.config import get_redis_settings


_database = None


def get_database_connection() -> redis.Redis:
    global _database

    if _database is None:
        settings = get_redis_settings()
        _database = redis.Redis(
            host=settings["host"],
            port=settings["port"],
            password=settings["password"],
            decode_responses=True,
        )

    return _database
