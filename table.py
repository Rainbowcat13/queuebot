import requests
from bs4 import BeautifulSoup
import json


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

d = dict()
for student in students:
    name = student[0]
    delays = list(reversed([student[i] for i in range(2, len(student), 4)]))[1:]
    d[name] = delays
json.dump(d, open('delays.json', 'w', encoding='utf8'), ensure_ascii=False)
