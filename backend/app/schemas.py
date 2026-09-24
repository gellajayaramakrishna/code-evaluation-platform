from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    is_admin: bool = False


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: str
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    rating: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TestCaseOut(BaseModel):
    id: int
    input_data: str
    expected_output: str
    is_sample: bool
    points: int

    model_config = ConfigDict(from_attributes=True)


class ProblemListOut(BaseModel):
    id: int
    slug: str
    title: str
    difficulty: str
    tags: str
    time_limit_ms: int
    memory_limit_mb: int

    model_config = ConfigDict(from_attributes=True)


class ProblemOut(ProblemListOut):
    statement: str
    input_spec: str
    output_spec: str
    constraints: str
    starter_python: str
    starter_cpp: str
    starter_java: str
    samples: list[TestCaseOut] = []


class SubmissionCreate(BaseModel):
    problem_id: int
    language: str
    source_code: str
    contest_id: Optional[int] = None
    assessment_id: Optional[int] = None


class SubmissionOut(BaseModel):
    id: int
    user_id: int
    problem_id: int
    contest_id: Optional[int]
    assessment_id: Optional[int]
    language: str
    source_code: str
    status: str
    verdict: str
    passed: int
    total: int
    runtime_ms: int
    memory_kb: int
    score: int
    compile_output: str
    result_json: str
    job_id: str
    created_at: datetime
    judged_at: Optional[datetime]
    username: Optional[str] = None
    problem_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ContestOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    is_public: bool
    status: str = "upcoming"
    problems: list[dict] = []

    model_config = ConfigDict(from_attributes=True)


class LeaderboardRow(BaseModel):
    rank: int
    username: str
    score: int
    penalty: int
    solved: int


class AssessmentOut(BaseModel):
    id: int
    slug: str
    company: str
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    lock_ai: bool
    status: str = "upcoming"
    problems: list[dict] = []

    model_config = ConfigDict(from_attributes=True)


class IntegrityEventIn(BaseModel):
    event_type: str
    detail: str = ""


class ExplainIn(BaseModel):
    source_code: str
    language: str
    problem_id: Optional[int] = None


class HintIn(BaseModel):
    problem_id: int
    source_code: Optional[str] = ""
    language: Optional[str] = "python"


class PlagiarismIn(BaseModel):
    submission_id: int


class MetricsOut(BaseModel):
    queue_depth: int
    priority_queue_depth: int
    pending_jobs: int
    workers: list[dict]
    submissions_total: int
    submissions_queued: int
    submissions_running: int
    avg_judge_ms: float
    uptime_s: float
