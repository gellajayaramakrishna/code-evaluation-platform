import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

export default function Home() {
  const [metrics, setMetrics] = useState(null);
  const [problems, setProblems] = useState([]);
  const [contest, setContest] = useState(null);

  useEffect(() => {
    api("/api/metrics").then(setMetrics).catch(() => {});
    api("/api/problems").then(setProblems).catch(() => {});
    api("/api/contests")
      .then((rows) => setContest(rows.find((c) => c.status === "live") || rows[0]))
      .catch(() => {});
  }, []);

  return (
    <div className="page">
      <section className="hero">
        <div>
          <div className="eyebrow">Distributed judge</div>
          <h1>
            Write it. Submit it.
            <br />
            <em>Watch it land.</em>
          </h1>
          <p className="lede">
            Aether is a LeetCode-class execution engine: Docker sandboxes, Redis Streams
            with crash recovery, live WebSocket verdicts, contest priority, and an honest
            integrity log for company screens.
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
            <Link to="/problems" className="btn gold">
              Open the arena
            </Link>
            <Link to="/register" className="btn">
              Join as demo
            </Link>
          </div>
        </div>
        <div className="hero-card">
          <div className="eyebrow">Live fabric</div>
          <h3 style={{ fontSize: 26, marginTop: 6 }}>Queue & workers</h3>
          <p className="lede" style={{ fontSize: 14, margin: "8px 0 0" }}>
            Backend: {metrics?.queue_backend || "booting"}. Unacked jobs stay in the
            pending entries list until another worker claims them.
          </p>
          <div className="stat-row">
            <div className="stat">
              <b>{metrics?.queue_depth ?? "—"}</b>
              <span>normal depth</span>
            </div>
            <div className="stat">
              <b>{metrics?.priority_queue_depth ?? "—"}</b>
              <span>contest priority</span>
            </div>
            <div className="stat">
              <b>{metrics?.judged ?? "—"}</b>
              <span>judged</span>
            </div>
          </div>
        </div>
      </section>

      {contest && (
        <Link to={`/contests/${contest.slug}`} className="card" style={{ display: "block", marginBottom: 28 }}>
          <div className="meta">
            <span className="eyebrow">{contest.status}</span>
            <span className="pill">priority queue</span>
          </div>
          <h3 style={{ fontSize: 28 }}>{contest.title}</h3>
          <p className="lede" style={{ fontSize: 14 }}>{contest.description}</p>
        </Link>
      )}

      <h2>Featured set</h2>
      <div className="grid cards" style={{ marginTop: 16 }}>
        {problems.slice(0, 6).map((p) => (
          <Link key={p.id} to={`/problems/${p.slug}`} className="card">
            <div className="meta">
              <span className={`diff ${p.difficulty}`}>{p.difficulty}</span>
              <span>{p.tags}</span>
            </div>
            <h3 style={{ fontSize: 22, marginTop: 12 }}>{p.title}</h3>
            <p className="lede" style={{ fontSize: 13, marginTop: 6 }}>
              {p.time_limit_ms} ms · {p.memory_limit_mb} MB
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
