import time
import requests


start = time.time()
r = requests.get("https://codeforces.com/api/problemset.problems").json()
if r['status'] != 'OK':
    raise ConnectionError("No connection with codefoces.con")
problems = r['result']['problems']

tasks : dict[int, list[dict]] = dict()

for problem in problems:
    if 'rating' not in problem or 'index' not in problem or 'name' not in problem or 'contestId' not in problem:
        continue
    if problem['rating'] not in tasks:
        tasks[problem['rating']] = []
    tasks[problem['rating']].append(problem)
