from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[int] = mapped_column(Integer, default=1500)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submissions = relationship("Submission", back_populates="user")
    contest_scores = relationship("ContestScore", back_populates="user")


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    difficulty: Mapped[str] = mapped_column(String(16), index=True)
    statement: Mapped[str] = mapped_column(Text)
    input_spec: Mapped[str] = mapped_column(Text, default="")
    output_spec: Mapped[str] = mapped_column(Text, default="")
    constraints: Mapped[str] = mapped_column(Text, default="")
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256)
    starter_python: Mapped[str] = mapped_column(Text, default="")
    starter_cpp: Mapped[str] = mapped_column(Text, default="")
    starter_java: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(255), default="")
    hint: Mapped[str] = mapped_column(Text, default="")
    editorial: Mapped[str] = mapped_column(Text, default="")
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    test_cases = relationship("TestCase", back_populates="problem", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="problem")


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    input_data: Mapped[str] = mapped_column(Text)
    expected_output: Mapped[str] = mapped_column(Text)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    points: Mapped[int] = mapped_column(Integer, default=10)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    problem = relationship("Problem", back_populates="test_cases")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    contest_id: Mapped[int | None] = mapped_column(ForeignKey("contests.id"), nullable=True, index=True)
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("assessments.id"), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(16))
    source_code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    verdict: Mapped[str] = mapped_column(String(32), default="Pending")
    passed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    runtime_ms: Mapped[int] = mapped_column(Integer, default=0)
    memory_kb: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    compile_output: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text, default="[]")
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="submissions")
    problem = relationship("Problem", back_populates="submissions")


class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    problems = relationship("ContestProblem", back_populates="contest", cascade="all, delete-orphan")
    scores = relationship("ContestScore", back_populates="contest", cascade="all, delete-orphan")


class ContestProblem(Base):
    __tablename__ = "contest_problems"
    __table_args__ = (UniqueConstraint("contest_id", "problem_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    letter: Mapped[str] = mapped_column(String(4), default="A")
    points: Mapped[int] = mapped_column(Integer, default=100)

    contest = relationship("Contest", back_populates="problems")
    problem = relationship("Problem")


class ContestScore(Base):
    __tablename__ = "contest_scores"
    __table_args__ = (UniqueConstraint("contest_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    penalty: Mapped[int] = mapped_column(Integer, default=0)
    solved: Mapped[int] = mapped_column(Integer, default=0)
    last_accept_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    contest = relationship("Contest", back_populates="scores")
    user = relationship("User", back_populates="contest_scores")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    company: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=90)
    lock_ai: Mapped[bool] = mapped_column(Boolean, default=True)
    invite_code: Mapped[str] = mapped_column(String(32), unique=True)

    problems = relationship("AssessmentProblem", back_populates="assessment", cascade="all, delete-orphan")
    sessions = relationship("AssessmentSession", back_populates="assessment", cascade="all, delete-orphan")


class AssessmentProblem(Base):
    __tablename__ = "assessment_problems"
    __table_args__ = (UniqueConstraint("assessment_id", "problem_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    points: Mapped[int] = mapped_column(Integer, default=100)

    assessment = relationship("Assessment", back_populates="problems")
    problem = relationship("Problem")


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"
    __table_args__ = (UniqueConstraint("assessment_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")

    assessment = relationship("Assessment", back_populates="sessions")
    user = relationship("User")
    events = relationship("IntegrityEvent", back_populates="session", cascade="all, delete-orphan")


class IntegrityEvent(Base):
    __tablename__ = "integrity_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("assessment_sessions.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session = relationship("AssessmentSession", back_populates="events")


class HintChunk(Base):
    __tablename__ = "hint_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    level: Mapped[int] = mapped_column(Integer, default=1)
