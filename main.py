from fastapi import FastAPI

from apps.random_photo.cache import PhotosInfoRedisWriter, PhotosInfoWriterInterface
from apps.random_photo.router import random_photo_router


photos_info_writer: PhotosInfoWriterInterface = PhotosInfoRedisWriter()
photos_info_writer.write()  # запись данных из csv файла в кеш redis


app = FastAPI()
app.include_router(random_photo_router, prefix="/random_photo", tags=["random_photo"])
