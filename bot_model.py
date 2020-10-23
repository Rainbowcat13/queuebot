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
collection_settings: Collection = db['settings']
