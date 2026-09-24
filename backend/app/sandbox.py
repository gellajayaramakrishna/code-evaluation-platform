"""Secure code execution.

Prefers Docker (non-root, resource-limited, no network). Falls back to a
tight subprocess sandbox when Docker is unavailable (local preview).
Container pooling reuses warm Python interpreters between jobs.
"""

from __future__ import annotations

import os
import resource
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

LANGS = {
    "python": {
        "ext": ".py",
        "image": "python:3.12-alpine",
        "compile": None,
        "run": ["python3", "main.py"],
        "filename": "main.py",
    },
    "cpp": {
        "ext": ".cpp",
        "image": "gcc:13-bookworm",
        "compile": ["g++", "-O2", "-std=c++17", "-o", "main", "main.cpp"],
        "run": ["./main"],
        "filename": "main.cpp",
    },
    "java": {
        "ext": ".java",
        "image": "eclipse-temurin:17-jdk-alpine",
        "compile": ["javac", "Main.java"],
        "run": ["java", "-Xmx128m", "Main"],
        "filename": "Main.java",
    },
}


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    exit_code: int
    runtime_ms: int
    memory_kb: int
    timed_out: bool
    compile_error: str = ""


def _docker_available() -> bool:
    if settings.sandbox_backend == "subprocess":
        return False
    if settings.sandbox_backend == "docker":
        return True
    return shutil.which("docker") is not None and _docker_ping()


def _docker_ping() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


class ContainerPool:
    """Warm-container pool for Python to cut cold-start latency."""

    def __init__(self, size: int = 2):
        self.size = size
        self._lock = threading.Lock()
        self._ids: list[str] = []
        self.enabled = False

    def warmup(self) -> None:
        if not _docker_available():
            return
        self.enabled = True
        for _ in range(self.size):
            cid = self._spawn()
            if cid:
                self._ids.append(cid)

    def _spawn(self) -> str | None:
        try:
            r = subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--network=none",
                    "--memory=256m",
                    "--cpus=0.5",
                    "--user=65534:65534",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,size=32m",
                    "python:3.12-alpine",
                    "sleep",
                    "3600",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
        return None

    def acquire(self) -> str | None:
        with self._lock:
            if self._ids:
                return self._ids.pop()
        return self._spawn() if self.enabled else None

    def release(self, cid: str) -> None:
        with self._lock:
            if len(self._ids) < self.size:
                self._ids.append(cid)
                return
        subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=10)

    def drain(self) -> None:
        with self._lock:
            ids = list(self._ids)
            self._ids.clear()
        for cid in ids:
            subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=10)


pool = ContainerPool()


def _limit_resources(memory_mb: int, cpu_s: int):
    def _inner():
        try:
            mem = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s))
            resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
            resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
            os.setsid()
        except Exception:
            pass

    return _inner


def _run_subprocess(
    workdir: Path,
    cmd: list[str],
    stdin: str,
    time_limit_ms: int,
    memory_mb: int,
) -> ExecResult:
    t0 = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workdir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=_limit_resources(memory_mb, max(1, time_limit_ms // 1000 + 1)),
        )
        try:
            stdout, stderr = proc.communicate(input=stdin, timeout=time_limit_ms / 1000 + 0.4)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), 9)
            except Exception:
                proc.kill()
            stdout, stderr = proc.communicate()
            code = -9
    except Exception as exc:
        return ExecResult("", str(exc), 1, int((time.perf_counter() - t0) * 1000), 0, False)
    runtime = int((time.perf_counter() - t0) * 1000)
    mem_kb = 0
    try:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        mem_kb = int(usage.ru_maxrss)
    except Exception:
        pass
    return ExecResult(
        stdout=stdout or "",
        stderr=stderr or "",
        exit_code=code if code is not None else 1,
        runtime_ms=runtime,
        memory_kb=mem_kb,
        timed_out=timed_out,
    )


def _run_docker(
    workdir: Path,
    lang: dict,
    stdin: str,
    time_limit_ms: int,
    memory_mb: int,
) -> ExecResult:
    name = f"aether-{uuid.uuid4().hex[:10]}"
    timeout_s = max(1, time_limit_ms // 1000 + 1)
    cmd = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        f"--memory={memory_mb}m",
        "--memory-swap={0}m".format(memory_mb),
        "--cpus=0.5",
        "--pids-limit=64",
        "--user=65534:65534",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=32m",
        "-v",
        f"{workdir}:/work:ro",
        "-w",
        "/work",
        "--name",
        name,
        lang["image"],
        *lang["run"],
    ]
    t0 = time.perf_counter()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout_s + 1,
        )
        code = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        code = -9
        stdout = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = "Time Limit Exceeded"
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=5)
    runtime = int((time.perf_counter() - t0) * 1000)
    return ExecResult(stdout or "", stderr or "", code, runtime, 0, timed_out)


def execute(
    language: str,
    source: str,
    stdin: str,
    time_limit_ms: int = 2000,
    memory_mb: int = 256,
) -> ExecResult:
    lang = LANGS.get(language)
    if not lang:
        return ExecResult("", f"Unsupported language: {language}", 1, 0, 0, False, compile_error="Unsupported language")

    use_docker = _docker_available()
    workdir = Path(tempfile.mkdtemp(prefix="aether-"))
    try:
        src_path = workdir / lang["filename"]
        src_path.write_text(source, encoding="utf-8")
        os.chmod(workdir, 0o755)

        if lang["compile"]:
            compile_cmd = lang["compile"]
            if use_docker:
                c = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--network=none",
                        "--memory=512m",
                        "--cpus=1",
                        "-v",
                        f"{workdir}:/work",
                        "-w",
                        "/work",
                        lang["image"],
                        *compile_cmd,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            else:
                c = subprocess.run(compile_cmd, cwd=str(workdir), capture_output=True, text=True, timeout=20)
            if c.returncode != 0:
                return ExecResult("", c.stderr, c.returncode, 0, 0, False, compile_error=c.stderr or c.stdout)

        runner = _run_docker if use_docker else _run_subprocess
        if use_docker:
            return _run_docker(workdir, lang, stdin, time_limit_ms, memory_mb)
        return _run_subprocess(workdir, lang["run"], stdin, time_limit_ms, memory_mb)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
