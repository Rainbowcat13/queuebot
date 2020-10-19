import pymongo
from pymongo.collection import Collection


def fill_students_db():
    mongo = pymongo.MongoClient('mongodb://localhost:27017/')
    db = mongo['queue']
    students: Collection = db['students']
    for student in open('students_1', 'r', encoding='utf8').read().splitlines():
        name = ' '.join(student.split()[:-1])
        group = student.split()[-1]
        students.insert_one({'name': name, 'group': group})
    mongo.close()


fill_students_db()
