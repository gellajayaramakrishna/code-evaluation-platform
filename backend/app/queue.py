"""Redis Streams job queue with in-memory fallback.

Streams + Consumer Groups give crash recovery: if a worker dies mid-job,
the message stays unacknowledged in the Pending Entries List and another
worker can XAUTOCLAIM it. The in-memory path is used when Redis is down
so local preview still works.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.config import settings

try:
    import redis
except ImportError:
    redis = None


@dataclass
class Job:
    job_id: str
    payload: dict
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    stream_id: str = ""


class _MemoryQueue:
    def __init__(self):
        self._priority: deque[Job] = deque()
        self._normal: deque[Job] = deque()
        self._pending: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._seen: set[str] = set()
        self.workers: dict[str, float] = {}

    def enqueue(self, payload: dict, priority: int = 0) -> str:
        job_id = payload.get("job_id") or uuid.uuid4().hex
        payload["job_id"] = job_id
        with self._lock:
            if job_id in self._seen:
                return job_id
            self._seen.add(job_id)
            job = Job(job_id=job_id, payload=payload, priority=priority)
            (self._priority if priority else self._normal).append(job)
        return job_id

    def dequeue(self, worker_id: str, block_ms: int = 200) -> Job | None:
        deadline = time.time() + block_ms / 1000
        while time.time() < deadline:
            with self._lock:
                self.workers[worker_id] = time.time()
                q = self._priority or self._normal
                if q:
                    job = q.popleft()
                    self._pending[job.job_id] = job
                    return job
            time.sleep(0.05)
        with self._lock:
            self.workers[worker_id] = time.time()
        return None

    def ack(self, job: Job, worker_id: str = "") -> None:
        with self._lock:
            self._pending.pop(job.job_id, None)

    def reclaim(self, idle_ms: int = 30_000) -> list[Job]:
        cutoff = time.time() - idle_ms / 1000
        reclaimed = []
        with self._lock:
            stale = [j for j in self._pending.values() if j.created_at < cutoff]
            for job in stale:
                self._pending.pop(job.job_id, None)
                (self._priority if job.priority else self._normal).appendleft(job)
                reclaimed.append(job)
        return reclaimed

    def depth(self) -> tuple[int, int, int]:
        with self._lock:
            return len(self._normal), len(self._priority), len(self._pending)

    def healthy_workers(self) -> list[dict]:
        now = time.time()
        with self._lock:
            return [
                {"id": wid, "last_seen": ts, "alive": now - ts < 15}
                for wid, ts in self.workers.items()
            ]


class _RedisQueue:
    def __init__(self, url: str):
        self.r = redis.Redis.from_url(url, decode_responses=True)
        self.r.ping()
        self.stream = settings.job_stream
        self.pstream = settings.priority_stream
        self.group = settings.consumer_group
        self._ensure_group(self.stream)
        self._ensure_group(self.pstream)
        self.workers: dict[str, float] = {}
        self._lock = threading.Lock()

    def _ensure_group(self, stream: str) -> None:
        try:
            self.r.xgroup_create(stream, self.group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def enqueue(self, payload: dict, priority: int = 0) -> str:
        job_id = payload.get("job_id") or uuid.uuid4().hex
        payload["job_id"] = job_id
        stream = self.pstream if priority else self.stream
        self.r.xadd(stream, {"data": json.dumps(payload), "job_id": job_id}, maxlen=10_000, approximate=True)
        return job_id

    def dequeue(self, worker_id: str, block_ms: int = 200) -> Job | None:
        with self._lock:
            self.workers[worker_id] = time.time()
        for stream in (self.pstream, self.stream):
            resp = self.r.xreadgroup(
                self.group,
                worker_id,
                {stream: ">"},
                count=1,
                block=max(1, block_ms // 2),
            )
            if resp:
                _sname, messages = resp[0]
                msg_id, fields = messages[0]
                data = json.loads(fields["data"])
                return Job(
                    job_id=data.get("job_id", fields.get("job_id", msg_id)),
                    payload=data,
                    priority=1 if stream == self.pstream else 0,
                    stream_id=msg_id,
                )
        return None

    def ack(self, job: Job, worker_id: str = "") -> None:
        stream = self.pstream if job.priority else self.stream
        if job.stream_id:
            self.r.xack(stream, self.group, job.stream_id)

    def reclaim(self, idle_ms: int = 30_000) -> list[Job]:
        jobs = []
        for stream, prio in ((self.pstream, 1), (self.stream, 0)):
            try:
                result = self.r.xautoclaim(
                    stream, self.group, settings.worker_id, min_idle_time=idle_ms, start_id="0-0", count=10
                )
                messages = result[1] if isinstance(result, (list, tuple)) else []
                for msg_id, fields in messages:
                    data = json.loads(fields["data"])
                    jobs.append(
                        Job(
                            job_id=data.get("job_id", msg_id),
                            payload=data,
                            priority=prio,
                            stream_id=msg_id,
                        )
                    )
            except Exception:
                continue
        return jobs

    def depth(self) -> tuple[int, int, int]:
        n = self.r.xlen(self.stream)
        p = self.r.xlen(self.pstream)
        pending = 0
        for stream in (self.stream, self.pstream):
            try:
                info = self.r.xpending(stream, self.group)
                pending += int(info.get("pending", 0) if isinstance(info, dict) else info[0])
            except Exception:
                pass
        return int(n), int(p), int(pending)

    def healthy_workers(self) -> list[dict]:
        now = time.time()
        with self._lock:
            local = [
                {"id": wid, "last_seen": ts, "alive": now - ts < 15}
                for wid, ts in self.workers.items()
            ]
        return local or [{"id": "redis-group", "last_seen": now, "alive": True}]


class JobQueue:
    def __init__(self):
        self.backend = "memory"
        self._impl: _MemoryQueue | _RedisQueue = _MemoryQueue()
        if settings.redis_url and redis is not None:
            try:
                self._impl = _RedisQueue(settings.redis_url)
                self.backend = "redis-streams"
            except Exception:
                self._impl = _MemoryQueue()
                self.backend = "memory"

    def enqueue(self, payload: dict, priority: int = 0) -> str:
        return self._impl.enqueue(payload, priority)

    def dequeue(self, worker_id: str, block_ms: int = 200) -> Job | None:
        return self._impl.dequeue(worker_id, block_ms)

    def ack(self, job: Job, worker_id: str = "") -> None:
        self._impl.ack(job, worker_id)

    def reclaim(self, idle_ms: int = 30_000) -> list[Job]:
        return self._impl.reclaim(idle_ms)

    def depth(self) -> tuple[int, int, int]:
        return self._impl.depth()

    def healthy_workers(self) -> list[dict]:
        return self._impl.healthy_workers()


queue = JobQueue()
