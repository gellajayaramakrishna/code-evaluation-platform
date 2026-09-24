import time

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Submission
from app.queue import queue
from app.worker import stats as worker_stats

router = APIRouter(prefix="/api/metrics", tags=["metrics"])
STARTED = time.time()


@router.get("")
def metrics(db: Session = Depends(get_db)):
    n, p, pending = queue.depth()
    total = db.query(func.count(Submission.id)).scalar() or 0
    queued = db.query(func.count(Submission.id)).filter(Submission.status == "queued").scalar() or 0
    running = db.query(func.count(Submission.id)).filter(Submission.status == "running").scalar() or 0
    avg = db.query(func.avg(Submission.runtime_ms)).filter(Submission.status == "done").scalar() or 0
    wstats = worker_stats()
    return {
        "queue_backend": queue.backend,
        "queue_depth": n,
        "priority_queue_depth": p,
        "pending_jobs": pending,
        "workers": queue.healthy_workers(),
        "submissions_total": total,
        "submissions_queued": queued,
        "submissions_running": running,
        "avg_runtime_ms": float(avg or 0),
        "last_judge_ms": wstats.get("last_ms", 0),
        "judged": wstats.get("judged", 0),
        "errors": wstats.get("errors", 0),
        "uptime_s": time.time() - STARTED,
    }
