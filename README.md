# Aether Judge

Aether Judge is a distributed code-evaluation platform built to explore how an online judge such as LeetCode or Codeforces can be designed behind the scenes.

The project separates the API from the execution workers, puts submissions on a Redis Streams queue, runs untrusted code inside a restricted sandbox, stores results in a relational database, and pushes verdict updates to the browser over WebSockets. It also includes contest and company-assessment workflows plus an AI layer for explanations, hints, and code-similarity signals.

## What is implemented

- FastAPI backend with JWT authentication
- PostgreSQL data model for users, problems, test cases, submissions, contests, and assessments
- Redis Streams + Consumer Groups for the submission queue
- Separate worker process with acknowledgement and pending-message recovery
- Priority stream for contest/assessment submissions
- Idempotent submission processing using unique job IDs and terminal-state checks
- Docker-based execution path with network isolation, CPU/memory/PID limits, non-root execution, read-only filesystem, and temporary writable storage
- Python, C++17, and Java 17 execution paths
- Judge verdicts for accepted, wrong answer, timeout, runtime error, memory limit, and compilation error
- Whitespace/token-normalized output comparison with floating-point tolerance
- Real-time submission updates through WebSockets
- Contest leaderboard and scoring
- Company assessment sessions with time windows and integrity-signal logging
- Rate limiting and basic security headers
- Metrics endpoint for queue depth, worker health, and judging statistics
- Groq-powered code explanations
- RAG-style hint retrieval with ChromaDB/Sentence Transformers when the optional AI dependencies are installed
- Code-similarity based plagiarism signals, intended for human review rather than automatic cheating decisions
- React + Monaco Editor frontend
- Postman collection for API testing
- Pytest coverage for the core API, judge, and queue behavior
- GitHub Actions for backend tests and frontend builds
- Locust load-test script for simulating 50 concurrent users

## Architecture

```text
Browser (React + Monaco)
          |
          v
     FastAPI API
      /       \
     v         v
PostgreSQL   Redis Streams
                |
          Consumer Group
                |
        +-------+-------+
        |               |
     Worker 1        Worker 2 ...
        |
        v
   Code Sandbox
        |
        v
 Verdict + metrics
        |
        +----> WebSocket ---> Browser
```

The worker is deliberately separated from the API so multiple workers can consume jobs from the same Redis Consumer Group. If a worker dies after receiving a message but before acknowledging it, the message remains pending and can be reclaimed by another worker with `XAUTOCLAIM`.

## Queue design

This project intentionally uses Redis Streams rather than a plain Redis list.

A submission is written to a stream and consumed through a Consumer Group. The worker acknowledges the message only after processing. Unacknowledged messages remain in the Pending Entries List, which gives the system a recovery path when a worker crashes.

There are two streams:

- normal submissions
- priority submissions for active contests/assessments

The worker checks the priority stream before the normal stream.

## Sandbox design

The preferred execution path uses Docker with:

- `--network=none`
- memory limits
- CPU limits
- PID limits
- non-root user
- read-only filesystem
- small writable `/tmp`
- per-execution temporary working directory
- explicit cleanup when a timeout occurs

A subprocess-based fallback exists for local development when Docker is unavailable. It is useful for development, but Docker is the intended isolation mechanism for untrusted submissions.

## AI layer

The AI layer is deliberately separated from the core judge so judging does not depend on an LLM being available.

Current pieces:

1. Code explanation using Groq / Llama 3.1 8B
2. Hint retrieval using ChromaDB and Sentence Transformers, with a lightweight local fallback
3. Code-similarity comparison using embeddings when available, with token-based similarity as a fallback

The plagiarism feature is treated as an integrity signal for human review, not as proof that a submission is cheating.

Optional AI dependencies:

```bash
cd backend
pip install -r requirements-ai.txt
```

## Contest and assessment modes

Contest mode supports multiple users, contest scoring, penalties, live leaderboard updates, and higher-priority judging for contest submissions.

Company Assessment Mode supports:

- custom assessment windows
- timed sessions
- custom problem sets
- automatic scoring
- AI locking during the active assessment window
- tab-switch / blur / visibility event logging
- paste/copy event logging
- complete submission history for later review

The integrity events are intentionally presented as signals for human review, not as a hard cheat-detection guarantee.

## Running locally

### Backend

```bash
cd backend
pip install -r requirements.txt
PYTHONPATH=. python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Or use:

```bash
chmod +x start.sh
./start.sh
```

API documentation is available at:

```text
http://localhost:8000/docs
```

Demo accounts are seeded for local development:

```text
demo / demo123
admin / admin123
```

## Docker Compose

The repository also contains a Compose setup for PostgreSQL, Redis, API, worker, and frontend services:

```bash
docker compose up --build
```

The Compose development configuration currently uses the subprocess sandbox so the application can run without giving the API container direct control over the host Docker daemon. For an actual deployment, the sandbox boundary should be designed separately rather than treating the Docker socket as a production security boundary.

## Testing

Backend tests:

```bash
cd backend
pytest -q
```

Load test:

```bash
locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 60s --host http://localhost:8000
```

The load-test script creates concurrent users and submits code to exercise the API, queue, workers, and judge path.

## CI

GitHub Actions runs the backend test suite and frontend production build on pushes and pull requests.

## Project direction

The next engineering work is focused on measuring the system rather than adding features blindly:

1. verify Redis Streams crash recovery with multiple workers
2. run the 50-user load test and identify the actual bottleneck
3. improve the slowest part found by the measurements
4. benchmark cold container startup
5. only then experiment with warm-container pooling
6. deepen the AI/RAG and plagiarism implementations after the execution pipeline is stable

This keeps the project grounded in measurable engineering trade-offs instead of treating every feature as a checkbox.
