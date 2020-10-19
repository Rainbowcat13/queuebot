import pymongo
from pymongo.collection import Collection
import requests
from bs4 import BeautifulSoup


def fill_students_db():
    mongo = pymongo.MongoClient('mongodb://localhost:27017/')
    db = mongo['queue']
    students: Collection = db['students']
    for student in open('students_1', 'r', encoding='utf8').read().splitlines():
        name = ' '.join(student.split()[:-1])
        group = student.split()[-1]
        students.insert_one({'name': name, 'group': group})
    mongo.close()


def update_homeworks():
    resp = requests.get('http://www.kgeorgiy.info/git/geo/prog-intro-2020/src/branch/master/README.md',
                        verify=False).text
    soup = BeautifulSoup(resp, features='html.parser')

    homeworks: Collection = pymongo.MongoClient('mongodb://localhost:27017/')['queue']['homeworks']
    for h2 in soup.find_all('h2'):
        hw = h2.text
        if homeworks.find_one({'name': hw}) is None:
            homeworks.insert_one({'name': hw})


fill_students_db()
update_homeworks()
