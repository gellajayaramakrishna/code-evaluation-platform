from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import ai as ai_mod
from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Assessment, AssessmentSession, HintChunk, Problem, Submission, User
from app.schemas import ExplainIn, HintIn, PlagiarismIn

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _ai_locked(db: Session, user: User) -> bool:
    now = datetime.now(timezone.utc)
    sessions = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.user_id == user.id, AssessmentSession.status == "active")
        .all()
    )
    for s in sessions:
        a = s.assessment
        if not a or not a.lock_ai:
            continue
        end = a.ends_at
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        start = s.started_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if now <= end:
            return True
    return False


@router.post("/explain")
def explain(body: ExplainIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _ai_locked(db, user):
        raise HTTPException(403, "AI features are locked during an active assessment")
    title = statement = ""
    if body.problem_id:
        p = db.get(Problem, body.problem_id)
        if p:
            title, statement = p.title, p.statement
    return ai_mod.explain_code(body.source_code, body.language, title, statement)


@router.post("/hint")
def hint(body: HintIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _ai_locked(db, user):
        raise HTTPException(403, "AI features are locked during an active assessment")
    p = db.get(Problem, body.problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    docs = [c.content for c in db.query(HintChunk).filter(HintChunk.problem_id == p.id).all()]
    if p.hint:
        docs.append(p.hint)
    if p.editorial:
        docs.append(p.editorial[:800])
        ai_mod.index_hints(p.id, docs)
    return ai_mod.generate_hint(
        p.title, p.statement, docs, body.source_code or "", body.language or "python", problem_id=p.id
    )


@router.post("/complexity")
def complexity(body: ExplainIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _ai_locked(db, user):
        raise HTTPException(403, "AI features are locked during an active assessment")
    return ai_mod.estimate_complexity(body.source_code, body.language)


@router.post("/plagiarism")
def plagiarism(body: PlagiarismIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    sub = db.get(Submission, body.submission_id)
    if not sub:
        raise HTTPException(404, "Submission not found")
    others = (
        db.query(Submission)
        .filter(
            Submission.problem_id == sub.problem_id,
            Submission.id != sub.id,
            Submission.language == sub.language,
        )
        .limit(80)
        .all()
    )
    payload = [
        {"id": o.id, "user_id": o.user_id, "username": o.user.username if o.user else "", "source_code": o.source_code}
        for o in others
    ]
    report = ai_mod.plagiarism_report(sub.source_code, payload)
    report["submission_id"] = sub.id
    report["disclaimer"] = "Similarity is an integrity signal for human review, not a cheat verdict."
    return report


@router.get("/status")
def status():
    return {
        "groq": bool(__import__("app.config", fromlist=["settings"]).settings.groq_api_key),
        "embeddings": bool(ai_mod._try_embedder()),
        "chromadb": bool(ai_mod._try_chroma()),
    }
