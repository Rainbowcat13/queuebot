import requests
from bs4 import BeautifulSoup
import json


class DelaysTable:

    def __init__(self):
        self.d = dict()
        self.load_delays()

    def set_delay(self, user_name: str, task_id: int, delay: bool):
        while len(self.d[user_name]) <= task_id:
            self.d[user_name].append("0")

        self.d[user_name][task_id] = "1" if delay else "0"

    def get_delay(self, user_name: str, task_id: int) -> bool:
        return False if len(self.d[user_name]) < task_id else self.d[user_name][task_id] == "1"

    def load_delays(self):
        try:
            self.d = json.load(open('delays.json', 'r', encoding='utf8'))
        except Exception as e:
            print(e)
            self.reload_delays()

    def reload_delays(self):
        print("reload delays table")
        resp = requests.get('https://docs.google.com/spreadsheets/d/e/2PACX-1vTMff1WQpAk66EMnZyA3cUCQr_'
                            '2scBkCLEJwwD7dYOmE1oI1XxOMgart8R0LjVj-39fnRi-lI8ixta2/pubhtml?gid=2006076710&single=true').text
        soup = BeautifulSoup(resp, features='html.parser')

        cnt = 0
        students = []
        cur_student = []
        for element in soup.find_all('td')[84:]:
            if cnt % 35 not in [1, 2, 3, 4]:
                cur_student.append(element.text)
            cnt += 1
            if cnt % 35 == 0:
                students.append(cur_student)
                cur_student = []

        self.d.clear()

        for student in students:
            name = student[0]
            delays = ["0"] + list(reversed([student[i] for i in range(2, len(student), 4)]))[1:]
            self.d[name] = delays
        self.dump()

    def dump(self):
        json.dump(self.d, open('delays.json', 'w', encoding='utf8'), ensure_ascii=False)


delays_table = DelaysTable()
