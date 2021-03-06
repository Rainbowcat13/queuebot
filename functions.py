import math
from time import time

from lesson_settings import lesson_settings


def real_user(update):
    return update.message.chat.type == "private"


def get_elapsed_time():
    t = max(math.ceil((lesson_settings['ending'] - time()) / 60), 0)
    endings = [' минут', ' минуты', ' минута']

    if t % 10 >= 5 or t % 10 == 0:
        t = str(t) + endings[0]
    elif t % 10 >= 2:
        t = str(t) + endings[1]
    else:
        t = str(t) + endings[2]
    return t


def get_homework_id(title: str) -> int:
    return int(title.split()[2][0:-1])


def get_homework_title_by_id(task_id: int):
    p = lesson_settings['actual_problems']

    for i in range(len(p)):
        if task_id == get_homework_id(p[i]):
            return p[i]

    return None
