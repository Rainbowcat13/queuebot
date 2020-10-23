import pymongo
from pymongo.collection import Collection
import requests
from bs4 import BeautifulSoup

MONGODB_CLIENT: str = open("config/mongo", "r").read()
STUDENTLISTFILE: str = "config/students"

def fill_students_db():
    mongo = pymongo.MongoClient(MONGODB_CLIENT)
    db = mongo['queue']
    students: Collection = db['students']
    for student in open(STUDENTLISTFILE, 'r', encoding='utf8').read().splitlines():
        name = ' '.join(student.split()[:-1])
        group = student.split()[-1]
        if students.find_one({'name': name, 'group': group}) is None:
            students.insert_one({'name': name, 'group': group})
    mongo.close()


def update_homeworks():
    resp = requests.get('http://www.kgeorgiy.info/git/geo/prog-intro-2020/src/branch/master/README.md',
                        verify=False).text
    soup = BeautifulSoup(resp, features='html.parser')

    homeworks: Collection = pymongo.MongoClient(MONGODB_CLIENT)['queue']['homeworks']
    for h2 in soup.find_all('h2'):
        hw = h2.text
        if homeworks.find_one({'name': hw}) is None:
            homeworks.insert_one({'name': hw})


if __name__ == "__main__":
    fill_students_db()
    update_homeworks()
