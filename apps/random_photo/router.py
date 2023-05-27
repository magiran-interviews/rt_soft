from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from redis import Redis

from connections.redis import redis_pool
from apps.random_photo.cache import PhotosInfoRedisGetter, PhotosInfoGetterInterface


def get_photo_getter() -> PhotosInfoGetterInterface:
    redis_conn = Redis(connection_pool=redis_pool)
    return PhotosInfoRedisGetter(conn=redis_conn)


random_photo_router = APIRouter()


@random_photo_router.get("/")
def get_random_photo(
        categories: list[str] = Query(max_length=10, default=[], alias="category"),
        photos_getter: PhotosInfoGetterInterface = Depends(get_photo_getter),
    ):
    random_photo = photos_getter.get_random_photo_from_categories(categories=categories) if categories \
        else photos_getter.get_random_photo_from_all_categories()

    html_code = f'<div><img src="{random_photo.url}"></div>'
    return JSONResponse({"html_code": html_code})
