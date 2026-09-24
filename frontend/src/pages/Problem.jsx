import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import Editor from "@monaco-editor/react";
import { api, currentUser, wsUrl } from "../lib/api";

const STARTERS = {
  python: "starter_python",
  cpp: "starter_cpp",
  java: "starter_java",
};

function verdictClass(v) {
  if (!v) return "";
  if (v === "Accepted") return "v-Accepted";
  if (v === "Pending" || v === "queued" || v === "running") return "v-Pending";
  return "v-Wrong";
}

export default function Problem({ contestId, assessmentId, lockAi }) {
  const { slug } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const [p, setP] = useState(null);
  const [lang, setLang] = useState("python");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [hint, setHint] = useState("");
  const [explain, setExplain] = useState("");
  const [err, setErr] = useState("");
  const socketRef = useRef(null);
  const cid = contestId || (sp.get("contest") ? Number(sp.get("contest")) : null);
  const aid = assessmentId || (sp.get("assessment") ? Number(sp.get("assessment")) : null);
  const aiLocked = Boolean(lockAi || aid);

  useEffect(() => {
    api(`/api/problems/${slug}`).then((d) => {
      setP(d);
      setCode(d.starter_python || "");
    });
  }, [slug]);

  useEffect(() => {
    if (!p) return;
    setCode(p[STARTERS[lang]] || "");
  }, [lang]);

  function listen(sid) {
    if (socketRef.current) socketRef.current.close();
    const ws = new WebSocket(wsUrl(`/api/submissions/ws/${sid}`));
    socketRef.current = ws;
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      setResult(msg);
      if (msg.status === "done") setBusy(false);
    };
  }

  async function submit() {
    if (!currentUser()) {
      nav("/login");
      return;
    }
    setErr("");
    setBusy(true);
    setResult({ status: "queued", verdict: "Pending" });
    try {
      const sub = await api("/api/submissions", {
        method: "POST",
        body: {
          problem_id: p.id,
          language: lang,
          source_code: code,
          contest_id: cid || undefined,
          assessment_id: aid || undefined,
        },
      });
      listen(sub.id);
    } catch (ex) {
      setErr(ex.message);
      setBusy(false);
    }
  }

  async function askHint() {
    setHint("Thinking…");
    try {
      const r = await api("/api/ai/hint", {
        method: "POST",
        body: { problem_id: p.id, source_code: code, language: lang },
      });
      setHint(r.hint);
    } catch (ex) {
      setHint(ex.message);
    }
  }

  async function askExplain() {
    setExplain("Thinking…");
    try {
      const r = await api("/api/ai/explain", {
        method: "POST",
        body: { problem_id: p.id, source_code: code, language: lang },
      });
      setExplain(r.explanation);
    } catch (ex) {
      setExplain(ex.message);
    }
  }

  const cases = useMemo(() => result?.cases || [], [result]);

  if (!p) return <div className="page">Loading…</div>;

  return (
    <div className="workspace">
      <aside className="statement">
        <div className="eyebrow">Problem {p.id}</div>
        <h2>{p.title}</h2>
        <div style={{ display: "flex", gap: 8, margin: "8px 0 16px" }}>
          <span className={`diff ${p.difficulty}`}>{p.difficulty}</span>
          <span className="pill">{p.time_limit_ms} ms</span>
          <span className="pill">{p.memory_limit_mb} MB</span>
        </div>
        <div className="prose">{p.statement}</div>
        {p.samples?.map((s, i) => (
          <div key={s.id} className="sample">
            <div className="eyebrow">Sample {i + 1}</div>
            <div>Input{"\n"}{s.input_data}</div>
            <div>Output{"\n"}{s.expected_output}</div>
          </div>
        ))}
        {!aiLocked && (
          <div style={{ marginTop: 18, display: "flex", gap: 8 }}>
            <button className="btn" onClick={askHint}>Nudge</button>
            <button className="btn" onClick={askExplain}>Explain my code</button>
          </div>
        )}
        {aiLocked && <div className="banner" style={{ marginTop: 16 }}>AI tools locked for this assessment window.</div>}
        {hint && <div className="hint-box">{hint}</div>}
        {explain && <div className="hint-box">{explain}</div>}
      </aside>
      <section className="editor-pane">
        <div className="toolbar">
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="python">Python 3</option>
            <option value="cpp">C++17</option>
            <option value="java">Java 17</option>
          </select>
          <div style={{ flex: 1 }} />
          <button className="btn gold" disabled={busy} onClick={submit}>
            {busy ? "Judging…" : "Submit"}
          </button>
        </div>
        <div className="editor-wrap">
          <Editor
            height="100%"
            theme="vs-dark"
            language={lang === "cpp" ? "cpp" : lang}
            value={code}
            onChange={(v) => setCode(v || "")}
            options={{ fontSize: 14, minimap: { enabled: false }, fontFamily: "IBM Plex Mono", padding: { top: 12 } }}
          />
        </div>
        <div className="results">
          {err && <div className="err">{err}</div>}
          {!result && <span style={{ color: "var(--muted)" }}>Submit to stream verdicts over WebSocket.</span>}
          {result && (
            <>
              <div>
                <span className={`verdict ${verdictClass(result.verdict || result.status)}`}>
                  {(result.verdict || result.status || "").toUpperCase()}
                </span>
                {result.total ? (
                  <span className="pill" style={{ marginLeft: 8 }}>
                    {result.passed}/{result.total} · {result.runtime_ms} ms
                  </span>
                ) : null}
              </div>
              {result.compile_output ? <pre className="sample">{result.compile_output}</pre> : null}
              {cases.map((c, i) => (
                <div key={c.case_id || i} style={{ marginTop: 8 }}>
                  <span className={`verdict ${verdictClass(c.verdict)}`}>{c.verdict}</span>
                  <span className="pill" style={{ marginLeft: 8 }}>
                    case {i + 1} · {c.runtime_ms} ms {c.is_sample ? "· sample" : ""}
                  </span>
                </div>
              ))}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
