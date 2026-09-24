import os
import sys
import time
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite:////tmp/aether_test_{os.getpid()}.db")
os.environ.setdefault("SANDBOX_BACKEND", "subprocess")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient

from app.main import app, init_db

init_db()
client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_register_login_and_solve_two_sum():
    name = "alice" + uuid.uuid4().hex[:8]
    r = client.post(
        "/api/auth/register",
        json={"username": name, "email": f"{name}@test.dev", "password": "secret1"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    problems = client.get("/api/problems").json()
    assert len(problems) >= 3
    two = next(p for p in problems if p["slug"] == "two-sum")
    detail = client.get(f"/api/problems/{two['slug']}").json()
    assert detail["samples"]

    src = (
        "n=int(input())\n"
        "a=list(map(int,input().split()))\n"
        "t=int(input())\n"
        "m={}\n"
        "for i,x in enumerate(a):\n"
        "    if t-x in m:\n"
        "        print(min(i,m[t-x]), max(i,m[t-x]))\n"
        "        break\n"
        "    m[x]=i\n"
    )
    sub = client.post(
        "/api/submissions",
        json={"problem_id": two["id"], "language": "python", "source_code": src},
        headers=headers,
    )
    assert sub.status_code == 200
    sid = sub.json()["id"]

    verdict = "Pending"
    for _ in range(40):
        got = client.get(f"/api/submissions/{sid}", headers=headers).json()
        if got["status"] == "done":
            verdict = got["verdict"]
            break
        time.sleep(0.25)
    assert verdict == "Accepted"


def test_login_wrong():
    r = client.post("/api/auth/login", data={"username": "nope", "password": "nope"})
    assert r.status_code == 401
