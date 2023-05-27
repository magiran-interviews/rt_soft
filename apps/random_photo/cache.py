from random import choice
from typing import NamedTuple, Self

from redis import Redis

from connections.redis import redis_pool
from settings import CSV_FILE_PATH, SITE_URL


__all__ = [
    "PhotosInfoWriterInterface",
    "PhotosInfoGetterInterface",
    "PhotosInfoRedisWriter",
    "PhotosInfoRedisGetter",
    "PhotoInfo"
]


class PhotoInfo(NamedTuple):
    url: str
    shows: int
    categories: frozenset

    @classmethod
    @property
    def null_object(self) -> Self:
        no_photo_url = PhotosCacheMixin.DEFAULT_PHOTO_URL
        return self(url=no_photo_url, shows=0, categories=frozenset())


def read_csv_file() -> list[str]:
    with open(CSV_FILE_PATH, "r") as file:
        data = file.read()
    return [line for line in data.split("\n") if line]


def parse_photos_info() -> list[PhotoInfo]:
    file_data = read_csv_file()

    result = [None] * len(file_data)
    for i in range(len(file_data)):
        line_arr = file_data[i].split(";")
        photo_info = PhotoInfo(
            url = line_arr[0],
            shows = int(line_arr[1]),
            categories = frozenset(line_arr[2:]),
        )
        result[i] = photo_info
    return result


class PhotosInfoWriterInterface:
    def write(self) -> None:
        raise NotImplementedError("Метод не имплементирован")


class PhotosInfoGetterInterface:
    def get_random_photo_from_categories(self, categories: list[str]) -> PhotoInfo:
        raise NotImplementedError("Метод не имплементирован")
    
    def get_random_photo_from_all_categories() -> PhotoInfo:
        raise NotImplementedError("Метод не имплементирован")


class PhotosCacheMixin:
    PHOTOS_KEY = "photos"
    CATEGORIES_NAMES_KEY = "categories_names"
    PREFIX_OF_CATEGORY_KEY = "category::"
    DEFAULT_PHOTO_URL = f"{SITE_URL}/static/no_photo.png"

    # получение значений через str.format()
    MAKE_CATEGORY_KEY = PREFIX_OF_CATEGORY_KEY + "{0}"

    def __init__(self, conn=None) -> None:
        self.redis_conn = conn if conn else Redis(connection_pool=redis_pool)


class PhotosInfoRedisWriter(PhotosInfoWriterInterface, PhotosCacheMixin):
    def write(self) -> None:
        """
        Записываем в кеш redis следующие структуры данных:

            description:
                Информация о фотограциях
            key:
                photos
            value
                dict({
                    "image_url_1": repr(image_1_info),
                    "image_url_2": repr(image_2_info),
                })
            
            description:
                Множество имён категорий фотографий
            key:
                categories_names
            value:
                set({"cat_name_1", "cat_name_2", "cat_name_3"})
                
            description:
                Множество url'ов фотограций (для каждой категории)
            key:
                category::<cat_name>
            value:
                set({"image_url_1", "image_url_2", "image_url_3"})
        """

        self.clear_cache()
        photos, categories_names, categories_items = self.get_structured_data()
        
        pipline = self.redis_conn.pipeline()
        pipline.hmset(self.PHOTOS_KEY, photos)
        pipline.sadd(self.CATEGORIES_NAMES_KEY, *categories_names)
        for cat_name, cat_images in categories_items.items():
            key = self.MAKE_CATEGORY_KEY.format(cat_name)
            pipline.sadd(key, *cat_images)
        pipline.execute()

    def clear_cache(self):
        self.redis_conn.delete(self.CATEGORIES_NAMES_KEY)
        self.redis_conn.delete(self.PHOTOS_KEY)
        for category_name in self.redis_conn.keys(f"{self.PREFIX_OF_CATEGORY_KEY}*"):
            self.redis_conn.delete(category_name)

    def get_structured_data(self) -> tuple[dict, set, dict]:
        photos = dict()
        categories_names = set()
        categories_items = dict()
        
        for photo_info in parse_photos_info():
            photos[photo_info.url] = repr(photo_info._asdict())
            categories_names = categories_names.union(photo_info.categories)
            for category in photo_info.categories:
                if category in categories_items:
                    categories_items[category].add(photo_info.url)
                else:
                    categories_items[category] = {photo_info.url}

        return photos, categories_names, categories_items

        
class PhotosInfoRedisGetter(PhotosInfoGetterInterface, PhotosCacheMixin):
    def get_random_photo_from_categories(self, categories: list[str]) -> PhotoInfo:
        """
        Выбираем случайное фото по след. правилу:
            - Получаем общий список фоток всех переданных категорий
            - Выбираем одну случайную фотку из этого списка
        """
        categories_keys = [self.MAKE_CATEGORY_KEY.format(cat_name) for cat_name in categories]
        all_photos = tuple(self.redis_conn.sunion(categories_keys))

        if len(all_photos) == 0:
            return PhotoInfo.null_object

        random_photo_url = choice(all_photos)
        random_photo_info = self.get_photo_info(random_photo_url)
        self.after_get_photo(random_photo_info)
        return random_photo_info
    
    def get_random_photo_from_all_categories(self) -> PhotoInfo:
        """
        Выбираем случайное фото по след. правилу:
            - Из списка всех изображений случайным образом выбираем одно
        """
        random_photo_url = self.redis_conn.hrandfield(self.PHOTOS_KEY)

        if random_photo_url is None:
            return PhotoInfo.null_object

        random_photo_info = self.get_photo_info(random_photo_url)
        self.after_get_photo(random_photo_info)
        return random_photo_info

    def get_photo_info(self, photo_url: str) -> PhotoInfo:
        photo_info_dump = self.redis_conn.hget(self.PHOTOS_KEY, photo_url)
        photo_info = eval(photo_info_dump)
        return PhotoInfo(**photo_info)
    
    def write_to_cache_photo_info(self, photo_info: dict):
        self.redis_conn.hset(self.PHOTOS_KEY, photo_info["url"], repr(photo_info))

    def after_get_photo(self, photo_info: PhotoInfo) -> None:
        """
        - По бизнес-логике учитываем, что фотка была показана
            - shows (кол-во отображений данной фото) уменьшаем на 1
            - если shows > 0
                - перезаписываем обновлённую статистику изображения в redis
            - если shows == 0
                - удаляем фото из множеств категорий где она присутствует
                - удаляем фото из списка photos
                - если в категории не осталось фото, удаляем категорию и имя категории из множества имён категорий
        """
        if photo_info.shows - 1 <= 0:
            for cat_name in photo_info.categories:
                cat_key = self.MAKE_CATEGORY_KEY.format(cat_name)
                self.redis_conn.srem(cat_key, photo_info.url)
                if self.redis_conn.scard(cat_key) == 0:
                    self.redis_conn.srem(self.CATEGORIES_NAMES_KEY, cat_name)
            self.redis_conn.hdel(self.PHOTOS_KEY, photo_info.url)
        else:
            photo_info = photo_info._asdict()
            photo_info["shows"] -= 1
            self.write_to_cache_photo_info(photo_info)
