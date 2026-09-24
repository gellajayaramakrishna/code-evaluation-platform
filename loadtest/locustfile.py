"""Simulate 50 concurrent submissions against the judge.

Usage:
  locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 60s --host http://localhost:8000
"""

import itertools

from locust import HttpUser, between, task

COUNTER = itertools.count()

SRC = """n=int(input())
a=list(map(int,input().split()))
t=int(input())
m={}
for i,x in enumerate(a):
    if t-x in m:
        print(min(i,m[t-x]), max(i,m[t-x]))
        break
    m[x]=i
"""


class JudgeUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        n = next(COUNTER)
        self.username = f"load{n}"
        r = self.client.post(
            "/api/auth/register",
            json={"username": self.username, "email": f"{self.username}@load.test", "password": "loadpass"},
        )
        if r.status_code != 200:
            r = self.client.post("/api/auth/login", data={"username": "demo", "password": "demo123"})
        token = r.json()["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {token}"})
        problems = self.client.get("/api/problems").json()
        self.pid = problems[0]["id"]

    @task(5)
    def submit(self):
        r = self.client.post(
            "/api/submissions",
            json={"problem_id": self.pid, "language": "python", "source_code": SRC},
        )
        if r.status_code == 200:
            sid = r.json()["id"]
            self.client.get(f"/api/submissions/{sid}")

    @task(2)
    def list_problems(self):
        self.client.get("/api/problems")

    @task(1)
    def metrics(self):
        self.client.get("/api/metrics")
