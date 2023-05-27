import random

from settings import CSV_FILE_PATH, SITE_URL


MAX_SHOWS_OF_PHOTO = 5
CATEGORIES = [
    "animals",
    "birds",
    "forest",
    "childrens",
    "clouds",
    "smartphones",
    "electronics",
    "music",
    "lakes",
    "computers",
    "school",
    "tourism",
    "fishing",
    "space",
    "science",
]
categories = CATEGORIES.copy()


def select_categories(max_categories_per_photo: int) -> list[str]:
    """Получаем случайное кол-во категорий в случайном порядке"""

    if max_categories_per_photo > len(CATEGORIES):
        raise ValueError("Запрашиваемое кол-во категорий больше, чем имеется")
    
    random.shuffle(categories)
    categories_cnt = random.randint(1, max_categories_per_photo)
    return categories[:categories_cnt]
    

def generate_csv(line_cnt: int):
    data = [None] * line_cnt
    for n in range(line_cnt):
        cur_categories = ";".join(select_categories(max_categories_per_photo=10))
        shows_cnt = random.randint(1, MAX_SHOWS_OF_PHOTO)
        data[n] = f"{SITE_URL}/static/image{n}.png;{shows_cnt};{cur_categories}\n"
    
    with open(CSV_FILE_PATH, "w") as file:
        file.writelines(data)


# generate_csv(line_cnt=30)
