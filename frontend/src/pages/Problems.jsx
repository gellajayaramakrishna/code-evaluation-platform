import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

export default function Problems() {
  const [rows, setRows] = useState([]);
  const [diff, setDiff] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const sp = new URLSearchParams();
    if (diff) sp.set("difficulty", diff);
    if (q) sp.set("q", q);
    api("/api/problems" + (sp.toString() ? `?${sp}` : "")).then(setRows).catch(() => setRows([]));
  }, [diff, q]);

  return (
    <div className="page">
      <div className="eyebrow">Catalog</div>
      <h1>Problems</h1>
      <div className="filters">
        {["", "Easy", "Medium", "Hard"].map((d) => (
          <button key={d || "all"} className={`btn ${diff === d ? "gold" : ""}`} onClick={() => setDiff(d)}>
            {d || "All"}
          </button>
        ))}
        <input className="field" placeholder="Search tags or title" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>#</th>
            <th>Title</th>
            <th>Difficulty</th>
            <th>Tags</th>
            <th>Limits</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id}>
              <td className="mono">{p.id}</td>
              <td>
                <Link to={`/problems/${p.slug}`}>{p.title}</Link>
              </td>
              <td>
                <span className={`diff ${p.difficulty}`}>{p.difficulty}</span>
              </td>
              <td className="mono">{p.tags}</td>
              <td className="mono">
                {p.time_limit_ms}ms / {p.memory_limit_mb}MB
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
