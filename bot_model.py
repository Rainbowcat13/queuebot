from pymongo.collection import Collection
import pymongo

TELEGRAMTOKEN: str = open('config/token', 'r').read()
MONGODB_CLIENT: str = open('config/mongo', 'r').read()
TEACHERS = ['Корнеев Георгий Александрович', 'Савон Юлия Константиновна', 'Плотников Андрей Игоревич']

mongo = pymongo.MongoClient(MONGODB_CLIENT)
db = mongo['queue']
collection_users: Collection = db['users']
collection_students: Collection = db['students']
collection_homeworks: Collection = db['homeworks']
collection_admins: Collection = db['admins']
collection_queues: Collection = db['queues']
collection_chats_with_broadcast: Collection = db['chats_with_broadcast']
# collection_settings: Collection = db['settings']
def find_one():
    return {
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
        'starting': 1603454400-40*60-3600,
        'ending': 1603454400,
    }
collection_settings = find_one()