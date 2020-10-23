import pymongo
from pymongo.collection import Collection
from bot_model import collection_students, collection_settings, collection_homeworks
import requests
from bs4 import BeautifulSoup

STUDENTLISTFILE: str = "config/students"

def fill_students_db():
    for student in open(STUDENTLISTFILE, 'r', encoding='utf8').read().splitlines():
        name = ' '.join(student.split()[:-1])
        group = student.split()[-1]
        if collection_students.find_one({'name': name, 'group': group}) is None:
            collection_students.insert_one({'name': name, 'group': group})

def set_setting():
    settings = {
        'actual_problems': [
            'Домашнее задание 4. Подсчет слов', 'Домашнее задание 5. Свой сканнер',
            'Домашнее задание 6. Подсчет слов++', 'Домашнее задание 7. Разметка',
        ],
        'problems_priority': {
            'Домашнее задание 4. Подсчет слов': 1,
            'Домашнее задание 5. Свой сканнер': 2,
            'Домашнее задание 6. Подсчет слов++': 3,
            'Домашнее задание 7. Разметка': 2,
        },
        'starting': 0,
        'ending': 1603454400,
    }
    if not collection_settings.find_one():
        collection_settings.insert_one(settings)
    else:
        collection_settings.update_one({}, {'$set': settings})

def update_homeworks():
    resp = requests.get('http://www.kgeorgiy.info/git/geo/prog-intro-2020/src/branch/master/README.md',
                        verify=False).text
    soup = BeautifulSoup(resp, features='html.parser')

    for h2 in soup.find_all('h2'):
        hw = h2.text
        if collection_homeworks.find_one({'name': hw}) is None:
            collection_homeworks.insert_one({'name': hw})


if __name__ == "__main__":
    fill_students_db()
    update_homeworks()
    # set_setting()