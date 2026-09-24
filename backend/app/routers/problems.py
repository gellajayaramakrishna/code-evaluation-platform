from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Problem, TestCase
from app.schemas import ProblemListOut, ProblemOut, TestCaseOut

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("", response_model=list[ProblemListOut])
def list_problems(difficulty: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Problem).filter(Problem.is_public.is_(True))
    if difficulty:
        query = query.filter(Problem.difficulty == difficulty)
    if q:
        like = f"%{q}%"
        query = query.filter(Problem.title.ilike(like) | Problem.tags.ilike(like))
    return query.order_by(Problem.id).all()


@router.get("/{slug}", response_model=ProblemOut)
def get_problem(slug: str, db: Session = Depends(get_db)):
    p = db.query(Problem).filter(Problem.slug == slug).first()
    if not p:
        try:
            p = db.query(Problem).filter(Problem.id == int(slug)).first()
        except ValueError:
            p = None
    if not p:
        raise HTTPException(404, "Problem not found")
    samples = (
        db.query(TestCase)
        .filter(TestCase.problem_id == p.id, TestCase.is_sample.is_(True))
        .order_by(TestCase.order_index)
        .all()
    )
    out = ProblemOut.model_validate(p)
    out.samples = [TestCaseOut.model_validate(s) for s in samples]
    return out
