"""AI layer: Groq explainer, RAG hints via ChromaDB, plagiarism via embeddings.

Falls back to deterministic local analysis when Groq / sentence-transformers
are unavailable so the product still works in preview.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from collections import Counter
from functools import lru_cache

from app.config import settings

_embedder = None
_chroma = None


def _try_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    try:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return _embedder
    except Exception:
        _embedder = False
        return None


def _try_chroma():
    global _chroma
    if _chroma is not None:
        return _chroma
    try:
        import chromadb

        os.makedirs(settings.chromadb_path, exist_ok=True)
        client = chromadb.PersistentClient(path=settings.chromadb_path)
        _chroma = client.get_or_create_collection("hints", metadata={"hnsw:space": "cosine"})
        return _chroma
    except Exception:
        _chroma = False
        return None


def tokenize_code(src: str) -> list[str]:
    src = re.sub(r"#.*", " ", src)
    src = re.sub(r"//.*", " ", src)
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.findall(r"[A-Za-z_]\w+|\d+|[+\-*/%<>=!&|^]+", src.lower())


def bow_vector(src: str) -> Counter:
    return Counter(tokenize_code(src))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _try_embedder()
    if model:
        return model.encode(texts, normalize_embeddings=True).tolist()
    vecs = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        vecs.append([(b - 128) / 128.0 for b in h[:32]])
    return vecs


def groq_chat(system: str, user: str) -> str | None:
    if not settings.groq_api_key:
        return None
    try:
        import httpx

        r = httpx.post(
            f"{settings.groq_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.groq_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
                "max_tokens": 700,
            },
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None
    return None


def local_explain(code: str, language: str, title: str) -> str:
    tokens = tokenize_code(code)
    loops = sum(1 for t in tokens if t in ("for", "while"))
    rec = "recursive" if "def" in tokens and tokens.count(title.lower().split()[0] if title else "") else ""
    has_sort = any(t in tokens for t in ("sort", "sorted"))
    has_map = any(t in tokens for t in ("dict", "map", "hashmap", "unordered_map"))
    has_dp = any(t in tokens for t in ("dp", "memo", "cache"))
    lines = [ln for ln in code.splitlines() if ln.strip()]
    parts = [
        f"This {language} solution for **{title or 'the problem'}** is {len(lines)} lines.",
        f"Control flow uses {loops} loop(s)" + (" and recursion." if rec else "."),
    ]
    if has_dp:
        parts.append("It looks like dynamic programming (memo / dp table detected).")
    elif has_map:
        parts.append("A hash map is used, typically pointing at O(n) average time.")
    elif has_sort:
        parts.append("Sorting is present, so the dominant cost is likely O(n log n).")
    else:
        parts.append("No heavy data structures detected; scan the loops to estimate complexity.")
    parts.append(
        "Walk through one sample input in your head, then check the early-return and off-by-one edges."
    )
    return " ".join(parts)


def explain_code(code: str, language: str, title: str = "", statement: str = "") -> dict:
    system = (
        "You are a concise programming tutor. Explain what the submitted code does, "
        "its approach, time/space complexity, and one possible improvement. "
        "Do not rewrite the full solution unless asked."
    )
    user = f"Problem: {title}\n{statement[:800]}\n\nLanguage: {language}\n\n```{language}\n{code[:4000]}\n```"
    text = groq_chat(system, user) or local_explain(code, language, title)
    return {"explanation": text, "provider": "groq" if settings.groq_api_key else "local"}


def estimate_complexity(code: str, language: str) -> dict:
    system = "Estimate Big-O time and space complexity. Reply as 'Time: O(...); Space: O(...)' plus one sentence."
    text = groq_chat(system, f"Language: {language}\n```\n{code[:3000]}\n```")
    if not text:
        tokens = tokenize_code(code)
        nested = 0
        depth = 0
        for t in tokens:
            if t in ("for", "while"):
                depth += 1
                nested = max(nested, depth)
            if t in ("if",):
                pass
        time_o = {0: "O(1)", 1: "O(n)", 2: "O(n^2)", 3: "O(n^3)"}.get(nested, "O(n^k)")
        if "sort" in tokens or "sorted" in tokens:
            time_o = "O(n log n)" if nested <= 1 else time_o
        text = f"Time: {time_o}; Space: O(n). Heuristic based on loop nesting and library calls."
    return {"estimate": text}


def index_hints(problem_id: int, chunks: list[str]) -> int:
    col = _try_chroma()
    ids = [f"p{problem_id}-{i}" for i in range(len(chunks))]
    if col:
        try:
            col.upsert(ids=ids, documents=chunks, metadatas=[{"problem_id": problem_id}] * len(chunks))
            return len(chunks)
        except Exception:
            pass
    return len(chunks)


@lru_cache(maxsize=256)
def _hint_store() -> dict:
    return {}


def retrieve_hints(problem_id: int, query: str, docs: list[str], k: int = 3) -> list[str]:
    col = _try_chroma()
    if col:
        try:
            res = col.query(query_texts=[query or "hint"], n_results=k, where={"problem_id": problem_id})
            found = (res.get("documents") or [[]])[0]
            if found:
                return found
        except Exception:
            pass
    if not docs:
        return []
    q = bow_vector(query or "algorithm approach complexity")
    ranked = sorted(docs, key=lambda d: cosine(q, bow_vector(d)), reverse=True)
    return ranked[:k]


def generate_hint(problem_title: str, statement: str, docs: list[str], code: str, language: str) -> dict:
    retrieved = retrieve_hints(0, code or statement[:200], docs)
    context = "\n".join(retrieved) if retrieved else statement[:600]
    system = (
        "Give a small nudge, not a full solution. One or two sentences. "
        "Stay at the conceptual level."
    )
    user = f"Problem {problem_title}\nContext:\n{context}\n\nStudent code ({language}):\n{code[:1500]}"
    text = groq_chat(system, user)
    if not text:
        if retrieved:
            text = retrieved[0]
        else:
            text = (
                f"Re-read the constraints for {problem_title}. "
                "Name the brute-force first, then look for the data structure that removes an inner loop."
            )
    return {"hint": text, "retrieved": retrieved, "provider": "groq" if settings.groq_api_key else "rag-local"}


def plagiarism_report(source: str, others: list[dict], threshold: float = 0.82) -> dict:
    if not others:
        return {"matches": [], "max_similarity": 0.0, "flagged": False}
    src_bow = bow_vector(source)
    matches = []
    for o in others:
        sim = cosine(src_bow, bow_vector(o["source_code"]))
        if _try_embedder():
            try:
                va, vb = embed_texts([source[:3000], o["source_code"][:3000]])
                dot = sum(x * y for x, y in zip(va, vb))
                sim = max(sim, float(dot))
            except Exception:
                pass
        matches.append(
            {
                "submission_id": o["id"],
                "user_id": o["user_id"],
                "username": o.get("username", ""),
                "similarity": round(sim, 4),
            }
        )
    matches.sort(key=lambda m: m["similarity"], reverse=True)
    top = matches[:8]
    mx = top[0]["similarity"] if top else 0.0
    return {"matches": top, "max_similarity": mx, "flagged": mx >= threshold}


def generate_tests(statement: str, samples: list[dict]) -> dict:
    system = (
        "Generate 3 extra edge-case test cases as JSON list of "
        "{\"input\": \"...\", \"output\": \"...\"}. No markdown."
    )
    user = f"{statement[:1200]}\nSamples: {samples[:2]}"
    text = groq_chat(system, user)
    return {"raw": text or "LLM unavailable. Add edge cases: empty input, max constraints, negatives."}
