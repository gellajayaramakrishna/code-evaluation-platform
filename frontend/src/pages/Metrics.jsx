import { useEffect, useState } from "react";
import { api } from "../lib/api";

export default function Metrics() {
  const [m, setM] = useState(null);
  useEffect(() => {
    const load = () => api("/api/metrics").then(setM).catch(() => {});
    load();
    const t = setInterval(load, 2500);
    return () => clearInterval(t);
  }, []);
  if (!m) return <div className="page">Loading fabric…</div>;
  return (
    <div className="page">
      <div className="eyebrow">Observability</div>
      <h1>Judge health</h1>
      <p className="lede">
        Queue backend <strong>{m.queue_backend}</strong>. Redis Streams keep unacked jobs in the
        PEL so a crashed worker does not drop work.
      </p>
      <div className="metrics">
        {[
          ["Queue", m.queue_depth],
          ["Priority", m.priority_queue_depth],
          ["Pending", m.pending_jobs],
          ["Judged", m.judged],
          ["Queued", m.submissions_queued],
          ["Running", m.submissions_running],
          ["Last judge ms", m.last_judge_ms],
          ["Uptime s", Math.round(m.uptime_s)],
        ].map(([k, v]) => (
          <div key={k} className="card stat">
            <b>{v}</b>
            <span>{k}</span>
          </div>
        ))}
      </div>
      <h3>Workers</h3>
      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {(m.workers || []).map((w) => (
            <tr key={w.id}>
              <td className="mono">{w.id}</td>
              <td>
                <span className={`live ${w.alive ? "" : "off"}`} />
                {w.alive ? "alive" : "stale"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
