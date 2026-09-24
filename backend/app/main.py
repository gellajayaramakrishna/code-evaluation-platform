import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.limiter import limiter
from app.routers import ai, assessments, auth, contests, metrics, problems, submissions
from app.seed import seed_if_empty
from app.worker import start_worker
from app.ws import hub


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    hub.set_loop(asyncio.get_running_loop())
    start_worker()
    yield


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    start_worker()


init_db()

app = FastAPI(title=settings.app_name, lifespan=lifespan, version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeaders)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(problems.router)
app.include_router(submissions.router)
app.include_router(contests.router)
app.include_router(assessments.router)
app.include_router(ai.router)
app.include_router(metrics.router)


@app.get("/api/health")
def health():
    return {"ok": True, "name": settings.app_name}


@app.get("/api/languages")
def languages():
    return [
        {"id": "python", "label": "Python 3", "monaco": "python"},
        {"id": "cpp", "label": "C++17", "monaco": "cpp"},
        {"id": "java", "label": "Java 17", "monaco": "java"},
    ]
