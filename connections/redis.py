from redis import ConnectionPool

from settings import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD


def create_redis_connection_pool():
    return ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )


redis_pool = create_redis_connection_pool()
