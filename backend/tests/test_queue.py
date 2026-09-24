from app.queue import _MemoryQueue


def test_priority_before_normal():
    q = _MemoryQueue()
    q.enqueue({"job_id": "n1", "submission_id": 1}, priority=0)
    q.enqueue({"job_id": "p1", "submission_id": 2}, priority=1)
    job = q.dequeue("w1", block_ms=50)
    assert job.job_id == "p1"
    q.ack(job)


def test_idempotent_enqueue():
    q = _MemoryQueue()
    a = q.enqueue({"job_id": "same", "submission_id": 1})
    b = q.enqueue({"job_id": "same", "submission_id": 1})
    assert a == b
    n, p, pending = q.depth()
    assert n + p == 1


def test_reclaim_stale():
    q = _MemoryQueue()
    q.enqueue({"job_id": "x", "submission_id": 1})
    job = q.dequeue("w1", block_ms=50)
    assert job is not None
    job.created_at = 0
    reclaimed = q.reclaim(idle_ms=1)
    assert len(reclaimed) == 1
    again = q.dequeue("w2", block_ms=50)
    assert again.job_id == "x"
