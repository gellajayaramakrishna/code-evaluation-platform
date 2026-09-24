import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import SessionLocal, get_db
from app.limiter import limiter
from app.models import Assessment, AssessmentSession, Contest, Problem, Submission, User
from app.queue import queue
from app.schemas import SubmissionCreate, SubmissionOut
from app.ws import hub

router = APIRouter(prefix="/api/submissions", tags=["submissions"])
ALLOWED = {"python", "cpp", "java"}


def _active_contest(db, contest_id: int) -> Contest:
    c = db.get(Contest, contest_id)
    if not c:
        raise HTTPException(404, "Contest not found")
    now = datetime.now(timezone.utc)
    start, end = c.starts_at, c.ends_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if now < start or now > end:
        raise HTTPException(400, "Contest is not active")
    return c


def _active_assessment(db, assessment_id: int, user_id: int) -> Assessment:
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    sess = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.assessment_id == assessment_id, AssessmentSession.user_id == user_id)
        .first()
    )
    if not sess or sess.status != "active":
        raise HTTPException(400, "No active assessment session")
    return a


def to_out(s: Submission) -> SubmissionOut:
    out = SubmissionOut.model_validate(s)
    out.username = s.user.username if s.user else None
    out.problem_title = s.problem.title if s.problem else None
    return out


@router.post("", response_model=SubmissionOut)
@limiter.limit("20/minute")
def create_submission(
    request: Request,
    body: SubmissionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.language not in ALLOWED:
        raise HTTPException(400, f"Language must be one of {sorted(ALLOWED)}")
    if len(body.source_code) > 64_000:
        raise HTTPException(400, "Source too large")
    problem = db.get(Problem, body.problem_id)
    if not problem:
        raise HTTPException(404, "Problem not found")

    priority = 0
    if body.contest_id:
        _active_contest(db, body.contest_id)
        priority = 1
    if body.assessment_id:
        _active_assessment(db, body.assessment_id, user.id)
        priority = 1

    job_id = uuid.uuid4().hex
    sub = Submission(
        user_id=user.id,
        problem_id=problem.id,
        contest_id=body.contest_id,
        assessment_id=body.assessment_id,
        language=body.language,
        source_code=body.source_code,
        status="queued",
        verdict="Pending",
        job_id=job_id,
        priority=priority,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    queue.enqueue(
        {
            "job_id": job_id,
            "submission_id": sub.id,
            "problem_id": problem.id,
            "language": body.language,
        },
        priority=priority,
    )
    return to_out(sub)


@router.get("", response_model=list[SubmissionOut])
def list_mine(
    problem_id: int | None = None,
    limit: int = Query(40, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Submission).filter(Submission.user_id == user.id)
    if problem_id:
        q = q.filter(Submission.problem_id == problem_id)
    rows = q.order_by(Submission.id.desc()).limit(limit).all()
    return [to_out(s) for s in rows]


@router.get("/{sid}", response_model=SubmissionOut)
def get_one(sid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(Submission, sid)
    if not s:
        raise HTTPException(404, "Not found")
    if s.user_id != user.id and not user.is_admin:
        raise HTTPException(403, "Forbidden")
    return to_out(s)


@router.websocket("/ws/{sid}")
async def submission_ws(ws: WebSocket, sid: int):
    topic = f"submission:{sid}"
    await hub.connect(ws, topic)
    db = SessionLocal()
    try:
        s = db.get(Submission, sid)
        if s:
            await ws.send_text(
                json.dumps(
                    {
                        "type": "snapshot",
                        "id": s.id,
                        "status": s.status,
                        "verdict": s.verdict,
                        "passed": s.passed,
                        "total": s.total,
                        "runtime_ms": s.runtime_ms,
                        "memory_kb": s.memory_kb,
                        "score": s.score,
                        "compile_output": s.compile_output,
                        "cases": json.loads(s.result_json or "[]"),
                    }
                )
            )
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        db.close()
        await hub.disconnect(ws, topic)
