import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, currentUser, getToken } from "../lib/api";

export default function Assessment() {
  const { slug } = useParams();
  const nav = useNavigate();
  const [info, setInfo] = useState(null);
  const [code, setCode] = useState("NORTHSTAR");
  const [remaining, setRemaining] = useState(0);
  const [err, setErr] = useState("");
  const [events, setEvents] = useState(0);
  const started = useRef(false);

  function log(event_type, detail) {
    if (!getToken() || !started.current) return;
    api(`/api/assessments/${slug}/events`, { method: "POST", body: { event_type, detail } }).then(() =>
      setEvents((n) => n + 1)
    ).catch(() => {});
  }

  useEffect(() => {
    const onBlur = () => log("window_blur", "window lost focus");
    const onVis = () => {
      if (document.hidden) log("tab_switch", "document.hidden");
      else log("visibility", "visible");
    };
    const onPaste = (e) => log("paste", `chars=${(e.clipboardData?.getData("text") || "").length}`);
    window.addEventListener("blur", onBlur);
    document.addEventListener("visibilitychange", onVis);
    document.addEventListener("paste", onPaste);
    return () => {
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("visibilitychange", onVis);
      document.removeEventListener("paste", onPaste);
    };
  }, [slug]);

  useEffect(() => {
    if (!remaining) return;
    const t = setInterval(() => setRemaining((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [remaining > 0]);

  async function start() {
    if (!currentUser()) {
      nav("/login");
      return;
    }
    setErr("");
    try {
      const r = await api(`/api/assessments/${slug}/start?invite_code=${encodeURIComponent(code)}`, { method: "POST" });
      started.current = true;
      setInfo(r.assessment);
      setRemaining(r.remaining_s);
    } catch (ex) {
      setErr(ex.message);
    }
  }

  const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
  const ss = String(remaining % 60).padStart(2, "0");

  return (
    <div className="page">
      <div className="eyebrow">Proctored window</div>
      <h1>{info?.title || "Company assessment"}</h1>
      {!started.current && (
        <div className="card" style={{ maxWidth: 520, marginTop: 16 }}>
          <p className="lede" style={{ fontSize: 14 }}>
            Invite code unlocks the set. AI explainer and hints stay locked. Focus and paste
            events are recorded for later human review.
          </p>
          <label>Invite code</label>
          <input className="field" value={code} onChange={(e) => setCode(e.target.value)} />
          {err && <div className="err">{err}</div>}
          <button className="btn gold" style={{ marginTop: 16 }} onClick={start}>
            Begin session
          </button>
        </div>
      )}
      {started.current && info && (
        <>
          <div className="banner">
            Time remaining {mm}:{ss} · integrity events logged {events} · AI locked
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Problem</th>
                <th>Difficulty</th>
                <th>Points</th>
              </tr>
            </thead>
            <tbody>
              {(info.problems || []).map((p) => (
                <tr key={p.id}>
                  <td>
                    <Link to={`/problems/${p.slug}?assessment=${info.id}`}>{p.title}</Link>
                  </td>
                  <td>
                    <span className={`diff ${p.difficulty}`}>{p.difficulty}</span>
                  </td>
                  <td>{p.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            className="btn"
            style={{ marginTop: 18 }}
            onClick={() => api(`/api/assessments/${slug}/submit`, { method: "POST" })}
          >
            Finish & lock submissions
          </button>
        </>
      )}
    </div>
  );
}
