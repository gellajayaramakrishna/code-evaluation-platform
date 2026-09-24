"""Judge worker: pull jobs from Redis Streams consumer group, execute, persist.

Idempotent: a job_id is unique. If a worker dies, XAUTOCLAIM / reclaim
hands the unacked message to another worker. Duplicate delivery is
skipped when the submission is already in a terminal state.
"""

from __future__ import annotations

import json
import threading
import time
import traceback
from datetime import datetime, timezone

from app.config import settings
from app.database import SessionLocal
from app.judge import judge_submission
from app.models import (
    AssessmentSession,
    Contest,
    ContestScore,
    Submission,
    TestCase,
)
from app.queue import Job, queue
from app.ws import hub

TERMINAL = {
    "Accepted",
    "Wrong Answer",
    "Time Limit Exceeded",
    "Runtime Error",
    "Memory Limit Exceeded",
    "Compilation Error",
}

_stop = threading.Event()
_thread: threading.Thread | None = None
_stats = {"judged": 0, "last_ms": 0, "errors": 0}


def stats() -> dict:
    return dict(_stats)


def _apply_contest_score(db, sub: Submission, verdict: str) -> None:
    if not sub.contest_id or verdict != "Accepted":
        return
    contest = db.get(Contest, sub.contest_id)
    if not contest:
        return
    row = (
        db.query(ContestScore)
        .filter(ContestScore.contest_id == sub.contest_id, ContestScore.user_id == sub.user_id)
        .first()
    )
    if not row:
        row = ContestScore(contest_id=sub.contest_id, user_id=sub.user_id)
        db.add(row)
        db.flush()
    already = (
        db.query(Submission)
        .filter(
            Submission.contest_id == sub.contest_id,
            Submission.user_id == sub.user_id,
            Submission.problem_id == sub.problem_id,
            Submission.verdict == "Accepted",
            Submission.id != sub.id,
        )
        .first()
    )
    if already:
        return
    starts = contest.starts_at
    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    penalty_min = max(0, int((now - starts).total_seconds() // 60))
    fails = (
        db.query(Submission)
        .filter(
            Submission.contest_id == sub.contest_id,
            Submission.user_id == sub.user_id,
            Submission.problem_id == sub.problem_id,
            Submission.verdict != "Accepted",
            Submission.status == "done",
            Submission.id != sub.id,
        )
        .count()
    )
    row.score += sub.score or 100
    row.solved += 1
    row.penalty += penalty_min + fails * 20
    row.last_accept_at = now


def _apply_assessment_score(db, sub: Submission) -> None:
    if not sub.assessment_id:
        return
    sess = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.assessment_id == sub.assessment_id,
            AssessmentSession.user_id == sub.user_id,
        )
        .first()
    )
    if not sess:
        return
    best = (
        db.query(Submission)
        .filter(
            Submission.assessment_id == sub.assessment_id,
            Submission.user_id == sub.user_id,
        )
        .all()
    )
    by_problem: dict[int, int] = {}
    for s in best:
        by_problem[s.problem_id] = max(by_problem.get(s.problem_id, 0), s.score)
    sess.score = sum(by_problem.values())


def process_job(job: Job) -> None:
    t0 = time.perf_counter()
    db = SessionLocal()
    try:
        payload = job.payload
        sub_id = int(payload["submission_id"])
        sub = db.get(Submission, sub_id)
        if not sub:
            return
        if sub.verdict in TERMINAL and sub.status == "done":
            return
        sub.status = "running"
        db.commit()
        try:
            hub.publish_sync(
                f"submission:{sub.id}",
                {"type": "status", "status": "running", "id": sub.id},
            )
        except Exception:
            pass

        cases = (
            db.query(TestCase)
            .filter(TestCase.problem_id == sub.problem_id)
            .order_by(TestCase.order_index, TestCase.id)
            .all()
        )
        tc_payload = [
            {
                "id": c.id,
                "input_data": c.input_data,
                "expected_output": c.expected_output,
                "is_sample": c.is_sample,
                "points": c.points,
            }
            for c in cases
        ]
        problem = sub.problem
        result = judge_submission(
            language=sub.language,
            source=sub.source_code,
            test_cases=tc_payload,
            time_limit_ms=problem.time_limit_ms,
            memory_limit_mb=problem.memory_limit_mb,
        )
        sub.status = "done"
        sub.verdict = result["verdict"]
        sub.passed = result["passed"]
        sub.total = result["total"]
        sub.runtime_ms = result["runtime_ms"]
        sub.memory_kb = result["memory_kb"]
        sub.score = result["score"]
        sub.compile_output = result["compile_output"]
        sub.result_json = result["result_json"]
        sub.judged_at = datetime.now(timezone.utc)
        _apply_contest_score(db, sub, result["verdict"])
        _apply_assessment_score(db, sub)
        db.commit()

        msg = {
            "type": "result",
            "id": sub.id,
            "status": "done",
            "verdict": sub.verdict,
            "passed": sub.passed,
            "total": sub.total,
            "runtime_ms": sub.runtime_ms,
            "memory_kb": sub.memory_kb,
            "score": sub.score,
            "compile_output": sub.compile_output,
            "cases": json.loads(sub.result_json or "[]"),
        }
        try:
            hub.publish_sync(f"submission:{sub.id}", msg)
            if sub.contest_id:
                hub.publish_sync(f"contest:{sub.contest_id}", {"type": "leaderboard"})
        except Exception:
            pass
        _stats["judged"] += 1
        _stats["last_ms"] = int((time.perf_counter() - t0) * 1000)
    except Exception:
        _stats["errors"] += 1
        traceback.print_exc()
        try:
            db.rollback()
            sub = db.get(Submission, int(job.payload.get("submission_id", 0)))
            if sub and sub.status != "done":
                sub.status = "done"
                sub.verdict = "Runtime Error"
                sub.compile_output = "Internal judge error"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def worker_loop(worker_id: str) -> None:
    last_reclaim = 0.0
    while not _stop.is_set():
        now = time.time()
        if now - last_reclaim > 10:
            for job in queue.reclaim(idle_ms=20_000):
                process_job(job)
                queue.ack(job, worker_id)
            last_reclaim = now
        job = queue.dequeue(worker_id, block_ms=400)
        if not job:
            continue
        process_job(job)
        queue.ack(job, worker_id)


def start_worker(worker_id: str | None = None) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    wid = worker_id or settings.worker_id
    _thread = threading.Thread(target=worker_loop, args=(wid,), name="aether-worker", daemon=True)
    _thread.start()


def stop_worker() -> None:
    _stop.set()
