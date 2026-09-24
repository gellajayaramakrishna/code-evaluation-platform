"""Judge: compare program output against expected test cases.

Verdicts: Accepted / Wrong Answer / Time Limit Exceeded /
Runtime Error / Memory Limit Exceeded / Compilation Error.
Whitespace-normalized comparison with optional floating-point tolerance.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from app.sandbox import ExecResult, execute


@dataclass
class CaseResult:
    case_id: int
    verdict: str
    runtime_ms: int
    memory_kb: int
    stdout: str
    stderr: str
    points: int
    is_sample: bool


FLOAT_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def _tokens(s: str) -> list[str]:
    return s.replace("\r\n", "\n").replace("\r", "\n").strip().split()


def outputs_equal(got: str, expected: str, abs_tol: float = 1e-6) -> bool:
    g, e = _tokens(got), _tokens(expected)
    if g == e:
        return True
    if len(g) != len(e):
        return False
    for a, b in zip(g, e):
        if a == b:
            continue
        if FLOAT_RE.match(a) and FLOAT_RE.match(b):
            try:
                if abs(float(a) - float(b)) <= abs_tol:
                    continue
            except ValueError:
                return False
        return False
    return True


def classify(result: ExecResult, expected: str, memory_limit_mb: int) -> str:
    if result.compile_error:
        return "Compilation Error"
    if result.timed_out:
        return "Time Limit Exceeded"
    if result.memory_kb > memory_limit_mb * 1024:
        return "Memory Limit Exceeded"
    if result.exit_code != 0:
        err = (result.stderr or "").lower()
        # Docker reports an OOM-killed process as exit code 137.
        # Timeout is checked above, so an un-timed-out 137 is treated as MLE.
        if result.exit_code == 137 or "out of memory" in err or "oom" in err:
            return "Memory Limit Exceeded"
        return "Runtime Error"
    if outputs_equal(result.stdout, expected):
        return "Accepted"
    return "Wrong Answer"


PRIORITY = [
    "Compilation Error",
    "Runtime Error",
    "Memory Limit Exceeded",
    "Time Limit Exceeded",
    "Wrong Answer",
    "Accepted",
]


def overall_verdict(cases: list[CaseResult]) -> str:
    if not cases:
        return "Runtime Error"
    worst = "Accepted"
    rank = {v: i for i, v in enumerate(PRIORITY)}
    for c in cases:
        if rank[c.verdict] < rank[worst]:
            worst = c.verdict
    return worst


def judge_submission(
    language: str,
    source: str,
    test_cases: list[dict],
    time_limit_ms: int,
    memory_limit_mb: int,
) -> dict:
    results: list[CaseResult] = []
    compile_output = ""
    max_runtime = 0
    max_mem = 0
    passed = 0
    score = 0

    for tc in test_cases:
        exe: ExecResult = execute(
            language=language,
            source=source,
            stdin=tc["input_data"],
            time_limit_ms=time_limit_ms,
            memory_mb=memory_limit_mb,
        )
        if exe.compile_error and not compile_output:
            compile_output = exe.compile_error
            cr = CaseResult(
                case_id=tc["id"],
                verdict="Compilation Error",
                runtime_ms=0,
                memory_kb=0,
                stdout="",
                stderr=exe.compile_error[:2000],
                points=0,
                is_sample=tc.get("is_sample", False),
            )
            results.append(cr)
            break
        verdict = classify(exe, tc["expected_output"], memory_limit_mb)
        pts = tc.get("points", 10) if verdict == "Accepted" else 0
        if verdict == "Accepted":
            passed += 1
            score += pts
        max_runtime = max(max_runtime, exe.runtime_ms)
        max_mem = max(max_mem, exe.memory_kb)
        results.append(
            CaseResult(
                case_id=tc["id"],
                verdict=verdict,
                runtime_ms=exe.runtime_ms,
                memory_kb=exe.memory_kb,
                stdout=(exe.stdout or "")[:4000],
                stderr=(exe.stderr or "")[:2000],
                points=pts,
                is_sample=tc.get("is_sample", False),
            )
        )
        if verdict in ("Compilation Error", "Runtime Error") and not tc.get("is_sample"):
            continue

    ov = overall_verdict(results)
    return {
        "verdict": ov,
        "passed": passed,
        "total": len(test_cases),
        "runtime_ms": max_runtime,
        "memory_kb": max_mem,
        "score": score,
        "compile_output": compile_output[:4000],
        "cases": [asdict(c) for c in results],
        "result_json": json.dumps([asdict(c) for c in results]),
    }
