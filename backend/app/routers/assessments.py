from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Assessment, AssessmentSession, IntegrityEvent, Submission, User
from app.schemas import AssessmentOut, IntegrityEventIn

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


def _status(a: Assessment) -> str:
    now = datetime.now(timezone.utc)
    start, end = a.starts_at, a.ends_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if now < start:
        return "upcoming"
    if now > end:
        return "ended"
    return "live"


def _to_out(a: Assessment, reveal: bool) -> AssessmentOut:
    problems = []
    if reveal:
        for ap in a.problems:
            problems.append(
                {
                    "id": ap.problem.id,
                    "slug": ap.problem.slug,
                    "title": ap.problem.title,
                    "difficulty": ap.problem.difficulty,
                    "points": ap.points,
                }
            )
    return AssessmentOut(
        id=a.id,
        slug=a.slug,
        company=a.company,
        title=a.title,
        description=a.description,
        starts_at=a.starts_at,
        ends_at=a.ends_at,
        duration_minutes=a.duration_minutes,
        lock_ai=a.lock_ai,
        status=_status(a),
        problems=problems,
    )


@router.get("", response_model=list[AssessmentOut])
def list_assessments(db: Session = Depends(get_db)):
    rows = db.query(Assessment).order_by(Assessment.starts_at.desc()).all()
    return [_to_out(a, reveal=False) for a in rows]


@router.post("/{slug}/start")
def start_session(slug: str, invite_code: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.slug == slug).first()
    if not a:
        raise HTTPException(404, "Assessment not found")
    if invite_code and invite_code != a.invite_code:
        raise HTTPException(403, "Invalid invite code")
    if _status(a) == "ended":
        raise HTTPException(400, "Assessment has ended")
    sess = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.assessment_id == a.id, AssessmentSession.user_id == user.id)
        .first()
    )
    if not sess:
        sess = AssessmentSession(assessment_id=a.id, user_id=user.id, status="active")
        db.add(sess)
        db.commit()
        db.refresh(sess)
    deadline = sess.started_at
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    deadline = deadline + timedelta(minutes=a.duration_minutes)
    now = datetime.now(timezone.utc)
    remaining = max(0, int((deadline - now).total_seconds()))
    if remaining == 0:
        sess.status = "expired"
        db.commit()
        raise HTTPException(400, "Time window expired")
    return {
        "session_id": sess.id,
        "remaining_s": remaining,
        "lock_ai": a.lock_ai,
        "assessment": _to_out(a, reveal=True),
    }


@router.get("/{slug}", response_model=AssessmentOut)
def get_one(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.slug == slug).first()
    if not a:
        raise HTTPException(404, "Not found")
    sess = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.assessment_id == a.id, AssessmentSession.user_id == user.id)
        .first()
    )
    return _to_out(a, reveal=bool(sess))


@router.post("/{slug}/events")
def log_event(
    slug: str,
    body: IntegrityEventIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = db.query(Assessment).filter(Assessment.slug == slug).first()
    if not a:
        raise HTTPException(404, "Not found")
    sess = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.assessment_id == a.id, AssessmentSession.user_id == user.id)
        .first()
    )
    if not sess:
        raise HTTPException(400, "Start the assessment first")
    allowed = {"tab_switch", "window_blur", "paste", "copy", "focus", "visibility"}
    if body.event_type not in allowed:
        raise HTTPException(400, "Unknown event type")
    db.add(IntegrityEvent(session_id=sess.id, event_type=body.event_type, detail=body.detail[:1000]))
    db.commit()
    return {"ok": True}


@router.post("/{slug}/submit")
def finish(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.slug == slug).first()
    if not a:
        raise HTTPException(404, "Not found")
    sess = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.assessment_id == a.id, AssessmentSession.user_id == user.id)
        .first()
    )
    if not sess:
        raise HTTPException(400, "No session")
    sess.status = "submitted"
    sess.submitted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "score": sess.score}


@router.get("/{slug}/review")
def review(slug: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    a = db.query(Assessment).filter(Assessment.slug == slug).first()
    if not a:
        raise HTTPException(404, "Not found")
    sessions = db.query(AssessmentSession).filter(AssessmentSession.assessment_id == a.id).all()
    out = []
    for s in sessions:
        events = [
            {"type": e.event_type, "detail": e.detail, "at": e.created_at.isoformat()}
            for e in s.events
        ]
        subs = (
            db.query(Submission)
            .filter(Submission.assessment_id == a.id, Submission.user_id == s.user_id)
            .order_by(Submission.id)
            .all()
        )
        out.append(
            {
                "user_id": s.user_id,
                "username": s.user.username if s.user else "",
                "score": s.score,
                "status": s.status,
                "started_at": s.started_at,
                "integrity_events": events,
                "submissions": [
                    {"id": x.id, "problem_id": x.problem_id, "verdict": x.verdict, "score": x.score}
                    for x in subs
                ],
                "note": "Integrity signal log for human review — not a hard cheat-detection guarantee.",
            }
        )
    return out
