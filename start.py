import requests
from bs4 import BeautifulSoup

from db import DBConnector


STUDENTLISTFILE: str = "config/students"
db = DBConnector()


def fill_students_db():
    for student in open(STUDENTLISTFILE, 'r', encoding='utf8').read().splitlines():
        name = ' '.join(student.split()[:-1])
        group = student.split()[-1]
        if db.aggregate_one('students', {'name': name, 'group': group}) is None:
            db.add_one('students', {'name': name, 'group': group})


def update_homeworks():
    resp = requests.get('http://www.kgeorgiy.info/git/geo/prog-intro-2020/src/branch/master/README.md',
                        verify=False).text
    soup = BeautifulSoup(resp, features='html.parser')

    for h2 in soup.find_all('h2'):
        hw = h2.text
        if db.aggregate_one('homeworks', {'name': hw}) is None:
            db.add_one('homeworks', {'name': hw})


if __name__ == "__main__":
    fill_students_db()
    update_homeworks()
