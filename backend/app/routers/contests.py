from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_optional_user
from app.database import SessionLocal, get_db
from app.models import Contest, ContestProblem, ContestScore, User
from app.schemas import ContestOut, LeaderboardRow
from app.ws import hub

router = APIRouter(prefix="/api/contests", tags=["contests"])


def _status(c: Contest) -> str:
    now = datetime.now(timezone.utc)
    start, end = c.starts_at, c.ends_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if now < start:
        return "upcoming"
    if now > end:
        return "ended"
    return "live"


def _to_out(c: Contest, include_problems: bool = True) -> ContestOut:
    problems = []
    if include_problems:
        for cp in sorted(c.problems, key=lambda x: x.letter):
            problems.append(
                {
                    "letter": cp.letter,
                    "points": cp.points,
                    "id": cp.problem.id,
                    "slug": cp.problem.slug,
                    "title": cp.problem.title,
                    "difficulty": cp.problem.difficulty,
                }
            )
    return ContestOut(
        id=c.id,
        slug=c.slug,
        title=c.title,
        description=c.description,
        starts_at=c.starts_at,
        ends_at=c.ends_at,
        is_public=c.is_public,
        status=_status(c),
        problems=problems,
    )


@router.get("", response_model=list[ContestOut])
def list_contests(db: Session = Depends(get_db)):
    rows = db.query(Contest).order_by(Contest.starts_at.desc()).all()
    return [_to_out(c, include_problems=False) for c in rows]


@router.get("/{slug}", response_model=ContestOut)
def get_contest(slug: str, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    c = db.query(Contest).filter(Contest.slug == slug).first()
    if not c:
        raise HTTPException(404, "Contest not found")
    out = _to_out(c, include_problems=True)
    if _status(c) == "upcoming" and not (user and user.is_admin):
        out.problems = []
    return out


@router.get("/{slug}/leaderboard", response_model=list[LeaderboardRow])
def leaderboard(slug: str, db: Session = Depends(get_db)):
    c = db.query(Contest).filter(Contest.slug == slug).first()
    if not c:
        raise HTTPException(404, "Contest not found")
    rows = (
        db.query(ContestScore)
        .filter(ContestScore.contest_id == c.id)
        .order_by(ContestScore.score.desc(), ContestScore.penalty.asc(), ContestScore.last_accept_at.asc())
        .all()
    )
    out = []
    for i, r in enumerate(rows, 1):
        out.append(
            LeaderboardRow(
                rank=i,
                username=r.user.username,
                score=r.score,
                penalty=r.penalty,
                solved=r.solved,
            )
        )
    return out


@router.post("/{slug}/join")
def join(slug: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.query(Contest).filter(Contest.slug == slug).first()
    if not c:
        raise HTTPException(404, "Contest not found")
    existing = (
        db.query(ContestScore).filter(ContestScore.contest_id == c.id, ContestScore.user_id == user.id).first()
    )
    if not existing:
        db.add(ContestScore(contest_id=c.id, user_id=user.id))
        db.commit()
    return {"ok": True, "status": _status(c)}


@router.websocket("/ws/{slug}")
async def contest_ws(ws: WebSocket, slug: str):
    db = SessionLocal()
    try:
        c = db.query(Contest).filter(Contest.slug == slug).first()
        topic = f"contest:{c.id}" if c else f"contest:{slug}"
    finally:
        db.close()
    await hub.connect(ws, topic)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws, topic)
